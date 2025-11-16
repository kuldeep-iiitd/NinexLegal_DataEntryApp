from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum, F
from django.utils import timezone
from datetime import datetime, time, date, timedelta, timezone as py_tz
from urllib.parse import urlparse

from cases.decorators import admin_required
from cases.models import Case, Employee, CaseType, State, CaseWork, AdHocFee
from Bank.models import Bank, BankBranch, BankStateCaseType
from .forms import BillingFilterForm
from django.http import JsonResponse


@admin_required
def dashboard(request):
    """Admin-only dashboard entry for Accounting/Billing and MIS."""
    return render(request, 'billing/dashboard.html')


def _fy_range(start_year: int):
    # Returns start_date, end_date for FY start_year-start_year+1 (Apr 1 to Mar 31)
    from datetime import date
    start = date(start_year, 4, 1)
    end = date(start_year + 1, 3, 31)
    return start, end


@admin_required
def billing_view(request):
    # No mutating POST actions in the new billing flow
    if request.method == 'POST':
        return redirect(request.get_full_path())

    form = BillingFilterForm(request.GET or None)
    export_format = (request.GET.get('format') or '').lower()
    results = []
    summary = {
        'total_cases': 0,
        'total_receipts': 0.0,
        'total_fees': 0.0,
        'total_extra_charges': 0.0,
        'grand_total': 0.0,
    }
    # Initialize variables used in context even when form is not valid or empty
    bank = None
    branch = None
    # Track max works across cases for dynamic columns
    max_works = 0
    # Always initialize work_indices for use in templates/exports even if form is invalid
    work_indices = []
    # Default queryset is empty to avoid unbound errors on invalid form
    qs = Case.objects.none()

    if form.is_valid():
        scope = form.cleaned_data['scope']
        bank = form.cleaned_data.get('bank')
        branch = form.cleaned_data.get('branch')
        case_type = form.cleaned_data.get('case_type')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        month = form.cleaned_data.get('month')
        year = form.cleaned_data.get('year')
        selected_cases = form.cleaned_data.get('cases')

        # Include both parent and child cases per new requirement
        qs = Case.objects.select_related('bank', 'case_type', 'branch')

        # Helper to build tz-aware UTC boundaries for a local (Asia/Kolkata) date span
        def local_span_to_utc_range(start_local_date: date, end_local_date: date):
            tz = timezone.get_fixed_timezone(330) if timezone.get_current_timezone_name() is None else timezone.get_current_timezone()
            # Start of day and end of day in local tz
            start_local_dt = datetime.combine(start_local_date, time.min)
            end_local_dt = datetime.combine(end_local_date, time.max)
            start_local_dt = timezone.make_aware(start_local_dt, tz)
            end_local_dt = timezone.make_aware(end_local_dt, tz)
            return start_local_dt.astimezone(py_tz.utc), end_local_dt.astimezone(py_tz.utc)

        # Filter by scope using tz-aware datetime ranges to avoid UTC/local mismatches
        if scope == 'bank' and bank:
            qs = qs.filter(bank=bank)
        elif scope == 'branch' and branch:
            qs = qs.filter(branch=branch)
        elif scope == 'date' and date_from and date_to:
            start_utc, end_utc = local_span_to_utc_range(date_from, date_to)
            qs = qs.filter(updated_at__range=(start_utc, end_utc))
        elif scope == 'month' and month and year:
            # First and last day of month
            first = date(year, month, 1)
            # Compute last day by going to next month then back one day
            if month == 12:
                last = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                last = date(year, month + 1, 1) - timedelta(days=1)
            start_utc, end_utc = local_span_to_utc_range(first, last)
            qs = qs.filter(updated_at__range=(start_utc, end_utc))
        elif scope == 'day' and date_from:
            start_utc, end_utc = local_span_to_utc_range(date_from, date_from)
            qs = qs.filter(updated_at__range=(start_utc, end_utc))
        elif scope == 'financial_year' and year:
            start, end = _fy_range(year)
            start_utc, end_utc = local_span_to_utc_range(start, end)
            qs = qs.filter(updated_at__range=(start_utc, end_utc))
        elif scope == 'custom' and selected_cases is not None:
            ids = list(selected_cases.values_list('id', flat=True))
            qs = Case.objects.select_related('bank', 'case_type', 'branch').filter(id__in=ids)

        # Restrict case types to those configured for the selected bank (or branch's bank) when not custom
        allowed_case_types = None
        if scope != 'custom' and branch:
            allowed_case_types = set(BankStateCaseType.objects.filter(bank=branch.bank).values_list('casetype_id', flat=True))
        elif scope != 'custom' and bank:
            allowed_case_types = set(BankStateCaseType.objects.filter(bank=bank).values_list('casetype_id', flat=True))
        if allowed_case_types is not None:
            qs = qs.filter(case_type_id__in=list(allowed_case_types))
        if case_type:
            qs = qs.filter(case_type=case_type)

        # Optional date range filter (applies in addition to scope)
        opt_from = form.cleaned_data.get('optional_date_from')
        opt_to = form.cleaned_data.get('optional_date_to')
        if opt_from and opt_to:
            start_utc, end_utc = local_span_to_utc_range(opt_from, opt_to)
            qs = qs.filter(updated_at__range=(start_utc, end_utc))
        elif opt_from and not opt_to:
            start_utc, end_dummy = local_span_to_utc_range(opt_from, opt_from)
            qs = qs.filter(updated_at__gte=start_utc)
        elif opt_to and not opt_from:
            dummy, end_utc = local_span_to_utc_range(opt_to, opt_to)
            qs = qs.filter(updated_at__lte=end_utc)

        # Helper to resolve a State object for a case, preferring branch.state when available,
        # else matching by name from Case.state (string field)
        def _resolve_case_state_obj(case):
            try:
                if getattr(case, 'branch_id', None) and getattr(case, 'branch', None) and getattr(case.branch, 'state_id', None):
                    return case.branch.state
            except Exception:
                pass
            try:
                if case.state:
                    return State.objects.filter(name__iexact=case.state).first()
            except Exception:
                return None
            return None

        for c in qs.order_by('-updated_at'):
            # Build flat list of (case type name, fee) including original and all extra works
            pairs = []
            work_items = []
            adhoc_items = []
            # Treat as quotation for billing if it was created as quotation or finalized from quotation flow
            is_quotation_case = bool(
                getattr(c, 'is_quotation', False)
                or getattr(c, 'status', '') == 'quotation'
                or getattr(c, 'quotation_finalized', False)
            )
            # Original item: allow custom override, else bank fee, else quotation price if quotation
            if is_quotation_case:
                base_fee = float(c.quotation_price or 0)
            else:
                if getattr(c, 'original_custom_fee', None) is not None:
                    base_fee = float(c.original_custom_fee or 0)
                else:
                    try:
                        state_obj = _resolve_case_state_obj(c)
                        if state_obj is not None:
                            bct = BankStateCaseType.objects.filter(bank=c.bank, state=state_obj, casetype=c.case_type).first()
                        else:
                            bct = BankStateCaseType.objects.filter(bank=c.bank, casetype=c.case_type).first()
                        base_fee = float(bct.fees) if bct else 0.0
                    except Exception:
                        base_fee = 0.0
            pairs.append({'name': c.case_type.name if c.case_type_id else '-', 'amount': base_fee})
            # Additional works with per-work custom override
            addl = list(CaseWork.objects.select_related('case_type').filter(case=c).order_by('created_at'))
            for w in addl:
                if getattr(w, 'custom_fee', None) is not None:
                    amt = float(w.custom_fee or 0)
                else:
                    try:
                        state_obj = _resolve_case_state_obj(c)
                        if state_obj is not None:
                            wbct = BankStateCaseType.objects.filter(bank=c.bank, state=state_obj, casetype=w.case_type).first()
                        else:
                            wbct = BankStateCaseType.objects.filter(bank=c.bank, casetype=w.case_type).first()
                        amt = float(wbct.fees) if wbct else 0.0
                    except Exception:
                        amt = 0.0
                pairs.append({'name': w.case_type.name, 'amount': amt})
                work_items.append({'id': w.id, 'name': w.case_type.name, 'amount': amt, 'custom': w.custom_fee})
            # Ad-hoc custom fee lines
            if not is_quotation_case:
                for af in AdHocFee.objects.filter(case=c).order_by('created_at'):
                    pairs.append({'name': af.name, 'amount': float(af.amount or 0)})
                    adhoc_items.append({'id': af.id, 'name': af.name, 'amount': float(af.amount or 0)})
            # Receipt
            rec_used = float(c.receipt_amount or 0)
            # Totals
            fees_total = sum(x['amount'] for x in pairs)
            total = fees_total + rec_used
            max_works = max(max_works, len(pairs))
            results.append({
                'case': c,
                'is_quotation': is_quotation_case,
                'works': pairs,
                'work_items': work_items,
                'adhoc_items': adhoc_items,
                'works_total': fees_total,
                'receipt': rec_used,
                'total': total,
            })
            summary['total_cases'] += 1
            summary['total_receipts'] += rec_used
            summary['total_fees'] += fees_total
            summary['grand_total'] += total

        # Pad works for table rendering and build an index list for headers
        work_indices = list(range(max_works)) if max_works > 0 else []
        for r in results:
            pad = max_works - len(r['works'])
            if pad > 0:
                r['works_padded'] = r['works'] + ([{'name': '', 'amount': 0.0}] * pad)
            else:
                r['works_padded'] = r['works']

    # Export handlers
    if export_format == 'csv' and results:
        import csv
        from django.http import HttpResponse
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="bill.csv"'
        w = csv.writer(resp)
        # Build dynamic columns as pivot by work name (e.g., LAP, Sun, etc.)
        # Also remove the "Original Case Type" column per requirement.
        base_headers = ['S.No', 'Case No', 'Applicant', 'Bank', 'LRN']
        # Ordered unique list of work names across all rows
        work_names = []
        seen = set()
        for r in results:
            for witem in r['works']:
                nm = (witem.get('name') or '').strip()
                if nm and nm not in seen:
                    seen.add(nm)
                    work_names.append(nm)
        tail_headers = ['Works Total', 'Receipt', 'Grand Total']
        w.writerow(base_headers + work_names + tail_headers)
        for i, r in enumerate(results, start=1):
            c = r['case']
            row = [
                i,
                c.case_number,
                c.applicant_name or '',
                c.bank.name if c.bank_id else '',
                c.legal_reference_number or '',
            ]
            # Map work name -> aggregated amount for this case
            amt_map = {}
            for witem in r['works']:
                nm = (witem.get('name') or '').strip()
                try:
                    val = float(witem.get('amount') or 0)
                except Exception:
                    val = 0.0
                if nm:
                    amt_map[nm] = (amt_map.get(nm, 0.0) + val)
            # Fill pivot columns in the same order as headers
            for nm in work_names:
                val = amt_map.get(nm)
                row.append(f"{val:.2f}" if val and abs(val) > 0 else '')
            row.extend([
                f"{r['works_total']:.2f}",
                f"{r['receipt']:.2f}",
                f"{r['total']:.2f}",
            ])
            w.writerow(row)
        return resp

    if export_format == 'print' and results:
        return render(request, 'billing/billing_print.html', {
            'form': form,
            'results': results,
            'summary': summary,
            'max_works': max_works,
            'work_indices': work_indices,
        })

    # If form is invalid, results remains empty and qs is none(); render page without crashing

    return render(request, 'billing/billing.html', {
        'form': form,
        'results': results,
        'summary': summary,
        'max_works': max_works,
        'work_indices': work_indices,
    })


@admin_required
def mis_view(request):
    """MIS case listing with essential fields, filters, and CSV export."""
    # Filters from query params
    mode = request.GET.get('by')  # bank | branch | employee | sro | advocate | case_type | state
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    bank_id = request.GET.get('bank')
    branch_id = request.GET.get('branch')
    employee_id = request.GET.get('employee')  # SRO
    advocate_id = request.GET.get('advocate')  # assigned_advocate
    case_type_id = request.GET.get('case_type')
    state_code = request.GET.get('state')  # for mode=state (string name)
    status = request.GET.get('status')
    search = request.GET.get('q')
    output_format = request.GET.get('format')  # 'csv' for export

    # Parse dates (filter by created_at to answer "when case came")
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = None
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = None

    # If mode not chosen yet, show selection screen (no query/rows)
    if not mode:
        # Step 1: only mode selection; no other controls or rows
        return render(request, 'billing/mis.html', {
            'mode': None,
            'rows': [],
            'banks': [],
            'branches': [],
            'employees': [],
            'advocates': [],
            'case_types': [],
            'states': [],
            'statuses': Case.STATUS_CHOICES,
            'start_date': '', 'end_date': '',
            'bank_selected': '', 'branch_selected': '', 'employee_selected': '', 'advocate_selected': '',
            'case_type_selected': '', 'state_selected': '', 'status_selected': '', 'q': ''
        })

    # Base queryset (include both root and child cases)
    qs = (
        Case.objects.select_related('bank', 'branch', 'employee', 'assigned_advocate', 'case_type')
        .order_by('-created_at')
    )

    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    # Apply selection semantics:
    # - If by=bank: require bank; optionally narrow to a branch of that bank.
    # - If by=branch: filter by branch (and implicitly the branch's bank).
    # - If by=employee: filter by employee (SRO).
    # - If by=case_type: filter by case type (optional bank filter allowed).
    if mode == 'bank':
        if bank_id:
            qs = qs.filter(bank_id=bank_id)
            if branch_id:
                qs = qs.filter(branch_id=branch_id)
    elif mode == 'branch':
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
    elif mode == 'employee' or mode == 'sro':
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
    elif mode == 'advocate':
        if advocate_id:
            qs = qs.filter(assigned_advocate_id=advocate_id)
    elif mode == 'case_type':
        if case_type_id:
            qs = qs.filter(case_type_id=case_type_id)
        if bank_id:
            qs = qs.filter(bank_id=bank_id)
    elif mode == 'state':
        # Prefer filtering by case.state (string); fallback to branch.state.name only if case.state is blank
        if state_code:
            qs = qs.filter(
                Q(state__iexact=state_code) |
                ((Q(state__isnull=True) | Q(state__exact='')) & Q(branch__state__name__iexact=state_code))
            )
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(case_number__icontains=search)
            | Q(legal_reference_number__icontains=search)
            | Q(applicant_name__icontains=search)
        )

    # Helper: financial year string from a date (Apr->Mar, e.g., 24.25)
    def fy_str(d: date | None) -> str:
        if not d:
            return ''
        y = d.year % 100
        if d.month < 4:
            y = (y - 1) % 100
        return f"{y:02d}.{(y+1)%100:02d}"

    # CSV export
    if output_format == 'csv':
        import csv
        from django.http import HttpResponse
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="MIS_Report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        writer = csv.writer(resp)
        writer.writerow([
            'S.No', 'DATE', 'BANK/NBFC', 'Branch', 'LRN No', 'FILE NO/LOAN NO',
            'APPLICANT NAME', 'Advocate Name', 'STATUS', 'Year', 'Receipt Number', 'Completed At'
        ])
        for i, c in enumerate(qs, start=1):
            # Resolve state label: prefer case.state string; else branch.state.name
            try:
                state_label = c.state or (c.branch.state.name if c.branch_id and c.branch and c.branch.state_id else '')
            except Exception:
                state_label = c.state or ''
            writer.writerow([
                i,
                (c.created_at.date() if c.created_at else ''),
                (c.bank.name if c.bank_id else ''),
                (c.branch.name if c.branch_id else ''),
                (c.legal_reference_number or ''),
                c.case_number,
                (c.applicant_name or ''),
                (c.assigned_advocate.name if c.assigned_advocate_id else ''),
                (c.get_status_display() if hasattr(c, 'get_status_display') else c.status),
                fy_str(c.created_at.date() if c.created_at else None),
                (c.receipt_number or ''),
                (c.completed_at.date() if c.completed_at else ''),
            ])
        return resp

    # For HTML, build a light list with computed FY (avoid heavy template logic)
    rows = []
    for c in qs[:1000]:  # cap for UI; CSV gives full
        rows.append({
            'obj': c,
            'date': c.created_at.date() if c.created_at else None,
            'bank': c.bank.name if c.bank_id else '',
            'branch': c.branch.name if c.branch_id else '',
            'lrn': c.legal_reference_number or '',
            'file_no': c.case_number,
            'applicant': c.applicant_name or '',
            'address': c.property_address or '',
            'advocate': c.assigned_advocate.name if c.assigned_advocate_id else '',
            'sro': c.employee.name if c.employee_id else '',
            'status': c.get_status_display() if hasattr(c, 'get_status_display') else c.status,
            'year': fy_str(c.created_at.date() if c.created_at else None),
            'receipt_number': c.receipt_number or '',
            'completed_at': c.completed_at.date() if c.completed_at else None,
            'case_type': c.case_type.name if c.case_type_id else '',
        })

    # Scope branch dropdown to selected bank when mode=bank
    branch_qs = BankBranch.objects.all()
    if mode == 'bank' and bank_id:
        branch_qs = branch_qs.filter(bank_id=bank_id)

    # States for dropdown: prefer State model; fallback to Case distinct values
    try:
        states_qs = State.objects.all().order_by('name')
    except Exception:
        states_qs = []

    advocates_qs = Employee.objects.filter(employee_type=Employee.ADVOCATE).order_by('name')
    sro_qs = Employee.objects.filter(employee_type=Employee.SRO).order_by('name')

    context = {
        'rows': rows,
        'mode': mode,
        'start_date': start_date_str or '',
        'end_date': end_date_str or '',
        'bank_selected': bank_id or '',
        'branch_selected': branch_id or '',
        'employee_selected': employee_id or '',
        'case_type_selected': case_type_id or '',
        'state_selected': state_code or '',
        'status_selected': status or '',
        'q': search or '',
    'banks': Bank.objects.all().order_by('name'),
    'branches': branch_qs.order_by('name'),
        'employees': sro_qs,
        'advocates': advocates_qs,
        'case_types': CaseType.objects.all().order_by('name'),
        'states': states_qs,
        'statuses': Case.STATUS_CHOICES,
    }
    return render(request, 'billing/mis.html', context)


@admin_required
def case_search_api(request):
    """AJAX: search cases by query string. Returns JSON array of {id, label}.
    Search across case_number, legal_reference_number, applicant_name.
    Optional bank/branch filters via query to constrain results if desired.
    """
    q = (request.GET.get('q') or '').strip()
    bank_id = request.GET.get('bank')
    branch_id = request.GET.get('branch')
    qs = Case.objects.all().order_by('-created_at')[:50]
    if bank_id:
        qs = qs.filter(bank_id=bank_id)
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
    if q:
        qs = qs.filter(
            Q(case_number__icontains=q)
            | Q(legal_reference_number__icontains=q)
            | Q(applicant_name__icontains=q)
        )
    data = [
        {
            'id': c.id,
            'label': f"{c.case_number} — {c.applicant_name or ''} ({c.bank.name if c.bank_id else ''})"
        }
        for c in qs[:25]
    ]
    return JsonResponse({'results': data})


@admin_required
def update_fees_api(request):
    """JSON endpoint to update fee overrides for a case.
    Expects: POST JSON with { case_id, original_custom_fee?, works: [{id, custom_fee?}], adhoc: [{id?, name, amount, _delete?}] }
    """
    import json
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    case_id = payload.get('case_id')
    if not case_id:
        return JsonResponse({'ok': False, 'error': 'case_id required'}, status=400)
    try:
        c = Case.objects.get(pk=case_id)
    except Case.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'case not found'}, status=404)
    # Update original fee
    if 'original_custom_fee' in payload:
        val = payload.get('original_custom_fee')
        try:
            from decimal import Decimal
            c.original_custom_fee = None if (val in [None,'',]) else Decimal(str(val))
        except Exception:
            return JsonResponse({'ok': False, 'error': 'invalid original_custom_fee'}, status=400)
        c.save(update_fields=['original_custom_fee'])
    # Update works fees
    for item in payload.get('works', []) or []:
        wid = item.get('id')
        try:
            w = CaseWork.objects.get(pk=wid, case=c)
        except CaseWork.DoesNotExist:
            continue
        if 'custom_fee' in item:
            val = item.get('custom_fee')
            try:
                from decimal import Decimal
                w.custom_fee = None if (val in [None,'']) else Decimal(str(val))
            except Exception:
                continue
            w.save(update_fields=['custom_fee'])
    # Adhoc create/update/delete
    for a in payload.get('adhoc', []) or []:
        if a.get('_delete') and a.get('id'):
            AdHocFee.objects.filter(pk=a['id'], case=c).delete()
            continue
        if a.get('id'):
            try:
                inst = AdHocFee.objects.get(pk=a['id'], case=c)
            except AdHocFee.DoesNotExist:
                continue
            name = a.get('name')
            amount = a.get('amount')
            if name is not None:
                inst.name = str(name)[:150]
            if amount is not None:
                try:
                    from decimal import Decimal
                    inst.amount = Decimal(str(amount))
                except Exception:
                    pass
            inst.save()
        else:
            name = (a.get('name') or '').strip()
            amount = a.get('amount')
            if name and amount is not None:
                try:
                    from decimal import Decimal
                    AdHocFee.objects.create(case=c, name=name[:150], amount=Decimal(str(amount)))
                except Exception:
                    pass
    return JsonResponse({'ok': True})
