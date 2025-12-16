from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from cases.models import Employee, Case
from django.utils import timezone
from django.db.models import Q, Count
import csv


def build_admin_stats():
    """Utility to gather high level admin statistics for dashboard and statistics page."""
    from cases.models import Case, Employee
    total_cases = Case.objects.count()
    pending_cases = Case.objects.filter(status__in=['pending_assignment', 'document_pending']).count()
    assigned_cases = Case.objects.filter(assigned_advocate__isnull=False).count()
    total_advocates = Employee.objects.filter(employee_type='advocate', is_active=True).count()
    return {
        'total_cases': total_cases,
        'pending_cases': pending_cases,
        'assigned_cases': assigned_cases,
        'total_advocates': total_advocates,
    }

@login_required
def dashboard(request):
    user = request.user
    
    
    is_admin = user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or user.is_superuser
    

    try:
        employee = Employee.objects.get(user=user)
        employee_id = employee.employee_id
        employee_type = employee.employee_type
        employee_name = employee.name
        
        
        if employee_type == 'advocate' and not is_admin:
            # Filter out child cases - only show parent cases
            assigned_cases = Case.objects.filter(assigned_advocate=employee, parent_case__isnull=True).order_by('-updated_at')
            # Separate child cases for independent trays
            assigned_child_cases = Case.objects.filter(assigned_advocate=employee, parent_case__isnull=False).order_by('-updated_at')
            total_cases = assigned_cases.count()
            active_cases = assigned_cases.filter(status__in=['draft','on_hold', 'on_query', 'query']).count()
            pending_cases_qs = assigned_cases.filter(status__in=['pending','draft'])
            pending_cases = pending_cases_qs.count()
            completed_cases = assigned_cases.filter(status__in=['positive', 'negative','positive_subject_tosearch']).count()
            doc_pending_count = assigned_cases.filter(status='document_pending').count()

            # Split pending into today vs overall (based on updated_at date)
            today = timezone.localdate()
            pending_today_list = pending_cases_qs.filter(updated_at__date=today)
            pending_overall_list = pending_cases_qs.exclude(id__in=pending_today_list.values('id'))

            # Completed cases categorized - only parent cases
            positive_cases = assigned_cases.filter(status='positive').order_by('-completed_at')
            positive_child_cases = assigned_child_cases.filter(status='positive').order_by('-completed_at')
            positive_subject_cases = assigned_cases.filter(status='positive_subject_tosearch').order_by('-completed_at')
            positive_subject_child_cases = assigned_child_cases.filter(status='positive_subject_tosearch').order_by('-completed_at')
            draft_positive_subject_cases = assigned_cases.filter(status='draft_positive_subject_tosearch').order_by('-completed_at')
            draft_positive_subject_child_cases = assigned_child_cases.filter(status='draft_positive_subject_tosearch').order_by('-completed_at')
            negative_cases = assigned_cases.filter(status='negative').order_by('-completed_at')
            negative_child_cases = assigned_child_cases.filter(status='negative').order_by('-completed_at')
            
            # SRO document pending cases - only parent cases
            sro_document_pending_cases = assigned_cases.filter(status='sro_document_pending').order_by('-updated_at')
            sro_document_pending_child_cases = assigned_child_cases.filter(status='sro_document_pending').order_by('-updated_at')
            sro_document_pending_total = sro_document_pending_cases.count() + sro_document_pending_child_cases.count()
            
            # Compute totals for completed categories (parent + child)
            positive_total = positive_cases.count() + positive_child_cases.count()
            positive_subject_total = positive_subject_cases.count() + positive_subject_child_cases.count()
            draft_positive_subject_total = draft_positive_subject_cases.count() + draft_positive_subject_child_cases.count()
            negative_total = negative_cases.count() + negative_child_cases.count()

            # Completed search (do not show full list by default)
            completed_search = (request.GET.get('completed_search') or '').strip()
            completed_results = []
            if completed_search:
                # Filter to only parent cases in search results too
                completed_results = assigned_cases.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch']).filter(
                    Q(applicant_name__icontains=completed_search) |
                    Q(case_number__icontains=completed_search) |
                    Q(legal_reference_number__icontains=completed_search)
                ).order_by('-updated_at')

            hold_query_doc_cases_list = assigned_cases.filter(status__in=['on_hold', 'on_query', 'query', 'document_pending'])

            context =  {
                "username": user.username,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "employee_type": employee_type,
                "employee": employee,
                "assigned_cases": assigned_cases,
                "assigned_child_cases": assigned_child_cases,
                "total_cases": total_cases,
                "active_cases": active_cases,
                "pending_cases": pending_cases,
                "completed_cases": completed_cases,
                "doc_pending_count": doc_pending_count,
                # Counters
                "pending_cases_list": pending_cases_qs,  # kept for header count
                "hold_query_doc_cases_list": hold_query_doc_cases_list,
                # New advocate-specific context
                "pending_today_list": pending_today_list,
                "pending_overall_list": pending_overall_list,
                "completed_search_query": completed_search,
                "completed_results": completed_results,
                # Completed categories
                "positive_cases": positive_cases,
                "positive_child_cases": positive_child_cases,
                "positive_total": positive_total,
                "positive_subject_cases": positive_subject_cases,
                "positive_subject_child_cases": positive_subject_child_cases,
                "positive_subject_total": positive_subject_total,
                "draft_positive_subject_cases": draft_positive_subject_cases,
                "draft_positive_subject_child_cases": draft_positive_subject_child_cases,
                "draft_positive_subject_total": draft_positive_subject_total,
                "negative_cases": negative_cases,
                "negative_child_cases": negative_child_cases,
                "negative_total": negative_total,
                "sro_document_pending_cases": sro_document_pending_cases,
                "sro_document_pending_child_cases": sro_document_pending_child_cases,
                "sro_document_pending_total": sro_document_pending_total,
            }
            return render(request, "accounts/employee_dashboard.html", context)


        if employee_type == 'sro' and not is_admin:
            # Get search query from request
            search_query = request.GET.get('search', '').strip()
            eligible_statuses = ['positive_subject_tosearch', 'negative', 'positive']
            # Independent listing (parents and children). Include PSTS automatically or explicitly forwarded cases.
            sro_cases = Case.objects.filter(
                Q(forwarded_to_sro=True) | Q(status='positive_subject_tosearch'),
                status__in=eligible_statuses
            ).order_by('-created_at')  # Newest cases first
            # Apply search filter if provided
            if search_query:
                sro_cases = sro_cases.filter(
                    Q(applicant_name__icontains=search_query) |
                    Q(case_number__icontains=search_query) |
                    Q(legal_reference_number__icontains=search_query)
                ).distinct()
            sro_pss_cases = sro_cases.filter(status='positive_subject_tosearch')
            sro_negative_cases = sro_cases.filter(status='negative')
            sro_positive_cases = sro_cases.filter(status='positive')
            
            context = {
                "username": user.username,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "employee_type": employee_type,
                "employee": employee,
                "is_admin": False,
                "is_sro": True,
                "sro_all_cases": sro_cases,
                "sro_total_cases": sro_cases.count(),
                "sro_pss_count": sro_pss_cases.count(),
                "sro_negative_count": sro_negative_cases.count(),
                "sro_positive_count": sro_positive_cases.count(),
                "sro_pss_cases": sro_pss_cases,
                "sro_negative_cases": sro_negative_cases,
                "sro_positive_cases": sro_positive_cases,
                "search_query": search_query,
            }
            return render(request, "accounts/sro_dashboard.html", context)

        # Admin dashboard with full statistics
        from Bank.models import Bank
        from datetime import timedelta
        stats = build_admin_stats()
        
        # Status cards for admin dashboard - all cases (parent and children)
        status_counts = Case.objects.values('status').annotate(count=Count('id')).order_by()
        status_dict = {row['status']: row['count'] for row in status_counts}
        
        active_cards_def = [
            ('draft','Draft'),
            ('quotation','Quotation'),
            ('pending_assignment','Pending Assign'),
            ('pending','Pending'),
            ('on_hold','On Hold'),
            ('query','Query'),
            ('document_pending','Doc Pending'),
        ]
        completed_cards_def = [
            ('positive_subject_tosearch','PSS'),
            ('draft_positive_subject_tosearch','Draft PSS'),
            ('positive','Positive'),
            ('negative','Negative'),
        ]
        status_cards_active = [
            {'key': k, 'label': lbl, 'count': status_dict.get(k, 0)}
            for (k, lbl) in active_cards_def
        ]
        status_cards_completed = [
            {'key': k, 'label': lbl, 'count': status_dict.get(k, 0)}
            for (k, lbl) in completed_cards_def
        ]
        
        # Advocate stats - only parent cases
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        advocates = Employee.objects.filter(employee_type='advocate', is_active=True)
        advocate_stats = []
        for adv in advocates:
            parent_cases = Case.objects.filter(assigned_advocate=adv)
            advocate_stats.append({
                'advocate': adv,
                'total_assigned': parent_cases.count(),
                'pending_count': parent_cases.filter(status__in=['pending','draft','on_hold','on_query','query','document_pending']).count(),
                'completed_today': parent_cases.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch'], updated_at__date=today).count(),
                'completed_yesterday': parent_cases.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch'], updated_at__date=yesterday).count(),
                'completed_7days': parent_cases.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch'], updated_at__date__gte=last_7_days).count(),
                'completed_30days': parent_cases.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch'], updated_at__date__gte=last_30_days).count(),
            })
        advocate_stats.sort(key=lambda x: x['pending_count'], reverse=True)
        
        # Bank stats - only parent cases
        banks = Bank.objects.all()
        bank_stats = []
        for bank in banks:
            parent_cases = Case.objects.filter(bank=bank)
            total = parent_cases.count()
            if total > 0:
                bank_stats.append({
                    'bank': bank,
                    'total_cases': total,
                    'active_cases': parent_cases.filter(status__in=['pending','draft','on_hold','on_query','query','document_pending','pending_assignment']).count(),
                    'completed_cases': parent_cases.filter(status__in=['positive','negative','positive_subject_tosearch']).count(),
                    'positive_cases': parent_cases.filter(status='positive').count(),
                    'negative_cases': parent_cases.filter(status='negative').count(),
                    'pss_cases': parent_cases.filter(status='positive_subject_tosearch').count(),
                })
        bank_stats.sort(key=lambda x: x['total_cases'], reverse=True)
        
        # Recent activity - only parent cases
        recent_completed = Case.objects.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch']).order_by('-updated_at')[:10]
        recent_assigned = Case.objects.filter(assigned_advocate__isnull=False).exclude(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch']).order_by('-updated_at')[:10]
        
        # Time-based stats - only parent cases
        cases_today = Case.objects.filter(created_at__date=today).count()
        cases_yesterday = Case.objects.filter(created_at__date=yesterday).count()
        cases_7days = Case.objects.filter(created_at__date__gte=last_7_days).count()
        cases_30days = Case.objects.filter(created_at__date__gte=last_30_days).count()
        
        completed_today = Case.objects.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch'], updated_at__date=today).count()
        completed_yesterday = Case.objects.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch'], updated_at__date=yesterday).count()
        completed_7days = Case.objects.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch'], updated_at__date__gte=last_7_days).count()
        completed_30days = Case.objects.filter(status__in=['positive','negative','positive_subject_tosearch','draft_positive_subject_tosearch'], updated_at__date__gte=last_30_days).count()
        
        context = {
            "username": user.username,
            "employee_id": employee_id,
            "employee_name": employee_name,
            "employee_type": employee_type,
            "employee": employee,
            **stats,
            "is_admin": is_admin,
            "status_cards_active": status_cards_active,
            "status_cards_completed": status_cards_completed,
            "advocate_stats": advocate_stats,
            "bank_stats": bank_stats,
            "today": today,
            "yesterday": yesterday,
            "recent_completed": recent_completed,
            "recent_assigned": recent_assigned,
            "cases_today": cases_today,
            "cases_yesterday": cases_yesterday,
            "cases_7days": cases_7days,
            "cases_30days": cases_30days,
            "completed_today": completed_today,
            "completed_yesterday": completed_yesterday,
            "completed_7days": completed_7days,
            "completed_30days": completed_30days,
        }
        return render(request, "accounts/dashboard.html", context)
        
    
    except Employee.DoesNotExist:
        if is_admin:
            messages.info(request, "Please create an Employee profile for yourself to access all features.")
            stats = build_admin_stats()
            
            # Status cards for admin dashboard
            from Bank.models import Bank
            status_counts = Case.objects.values('status').annotate(count=Count('id')).order_by()
            status_dict = {row['status']: row['count'] for row in status_counts}
            
            active_cards_def = [
                ('draft','Draft'),
                ('quotation','Quotation'),
                ('pending_assignment','Pending Assign'),
                ('pending','Pending'),
                ('on_hold','On Hold'),
                ('on_query','On Query'),
                ('query','Query'),
                ('document_pending','Doc Pending'),
            ]
            completed_cards_def = [
                ('positive_subject_tosearch','PSS'),
                ('positive','Positive'),
                ('negative','Negative'),
            ]
            status_cards_active = [
                {'key': k, 'label': lbl, 'count': status_dict.get(k, 0)}
                for (k, lbl) in active_cards_def
            ]
            status_cards_completed = [
                {'key': k, 'label': lbl, 'count': status_dict.get(k, 0)}
                for (k, lbl) in completed_cards_def
            ]
            
            # Advocate stats
            today = timezone.localdate()
            advocates = Employee.objects.filter(employee_type='advocate', is_active=True)
            advocate_stats = advocates.annotate(
                total_assigned=Count('assigned_cases', distinct=True),
                pending_count=Count('assigned_cases', filter=Q(assigned_cases__status__in=['pending','draft','on_hold','on_query','document_pending']), distinct=True),
                completed_today=Count('assigned_cases', filter=Q(assigned_cases__status__in=['positive','negative','positive_subject_tosearch']) & Q(assigned_cases__updated_at__date=today), distinct=True),
            ).order_by('-pending_count')
            
            # Bank stats
            bank_case_counts = Bank.objects.annotate(total_cases=Count('cases')).order_by('-total_cases')[:10]
            bank_active_counts = Bank.objects.annotate(active_cases=Count('cases', filter=Q(cases__status__in=['pending','on_hold','on_query','query','document_pending']))).order_by('-active_cases')[:10]
            
            context = {
                "username": user.username,
                "employee_id": f"ADMIN-{user.id}",
                **stats,
                "is_admin": is_admin,
                "status_cards_active": status_cards_active,
                "status_cards_completed": status_cards_completed,
                "advocate_stats": advocate_stats,
                "bank_case_counts": bank_case_counts,
                "bank_active_counts": bank_active_counts,
                "today": today,
            }
            return render(request, "accounts/dashboard.html", context)
        else:
            messages.warning(request, "You don't have administrative privileges. Contact admin for access.")
            context = {
                "username": user.username,
                "employee_id": user.id,
                "is_admin": False,
            }
            return render(request, "accounts/dashboard.html", context)


@login_required
def admin_statistics(request):
    user = request.user
    is_admin = user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or user.is_superuser
    if not is_admin:
        messages.error(request, "You don't have access to the statistics page.")
        return redirect('dashboard')

    # Case status counts overall
    from cases.models import Case, Employee
    from Bank.models import Bank
    status_counts = Case.objects.values('status').annotate(count=Count('id')).order_by()
    status_dict = {row['status']: row['count'] for row in status_counts}

    active_cards_def = [
        ('draft','Draft','bg-gray-100'),
        ('quotation','Quotation','bg-gray-100'),
        ('pending_assignment','Pending Assign','bg-orange-100'),
        ('pending','Pending','bg-purple-100'),
        ('on_hold','On Hold','bg-blue-100'),
        ('on_query','On Query','bg-yellow-100'),
        ('query','Query','bg-yellow-100'),
        ('document_pending','Doc Pending','bg-indigo-100'),
    ]
    completed_cards_def = [
        ('positive_subject_tosearch','PSS','bg-emerald-100'),
        ('positive','Positive','bg-emerald-100'),
        ('negative','Negative','bg-red-100'),
    ]
    status_cards_active = [
        {'key': k, 'label': lbl, 'color': color, 'count': status_dict.get(k, 0)}
        for (k, lbl, color) in active_cards_def
    ]
    status_cards_completed = [
        {'key': k, 'label': lbl, 'color': color, 'count': status_dict.get(k, 0)}
        for (k, lbl, color) in completed_cards_def
    ]

    # Per-advocate: pending and completed today
    today = timezone.localdate()
    advocates = Employee.objects.filter(employee_type='advocate', is_active=True)
    advocate_stats = advocates.annotate(
        total_assigned=Count('assigned_cases', distinct=True),
        pending_count=Count('assigned_cases', filter=Q(assigned_cases__status__in=['pending','draft','on_hold','on_query','query','document_pending']), distinct=True),
        completed_today=Count('assigned_cases', filter=Q(assigned_cases__status__in=['positive','negative','positive_subject_tosearch']) & Q(assigned_cases__updated_at__date=today), distinct=True),
    ).order_by('-pending_count')

    # Top banks by total cases
    bank_case_counts = Bank.objects.annotate(total_cases=Count('cases')).order_by('-total_cases')[:10]

    # Banks with active cases
    bank_active_counts = Bank.objects.annotate(active_cases=Count('cases', filter=Q(cases__status__in=['pending','draft','on_hold','on_query','query','document_pending']))).order_by('-active_cases')[:10]

    # Summary stats for header - include all cases (parent and children)
    total_cases = Case.objects.count()
    active_cases = Case.objects.filter(status__in=['pending','draft','on_hold','on_query','query','document_pending']).count()
    completed_cases = Case.objects.filter(status__in=['positive','negative','positive_subject_tosearch']).count()

    context = {
        'is_admin': True,
        'status_counts': status_dict,
        'status_cards_active': status_cards_active,
        'status_cards_completed': status_cards_completed,
        'advocate_stats': advocate_stats,
        'bank_case_counts': bank_case_counts,
        'bank_active_counts': bank_active_counts,
        'today': today,
        'total_cases': total_cases,
        'active_cases': active_cases,
        'completed_cases': completed_cases,
    }
    return render(request, 'accounts/admin_statistics.html', context)


@login_required
def cases_by_status(request, status):
    """View to show all cases for a specific status"""
    user = request.user
    is_admin = user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or user.is_superuser
    if not is_admin:
        messages.error(request, "You don't have access to this page.")
        return redirect('dashboard')
    
    # Only show parent cases
    cases = Case.objects.filter(status=status).select_related('assigned_advocate', 'bank', 'branch').order_by('-updated_at')
    
    status_labels = {
        'draft': 'Draft',
        'quotation': 'Quotation',
        'pending_assignment': 'Pending Assignment',
        'pending': 'Pending',
        'on_hold': 'On Hold',
        'on_query': 'On Query',
        'query': 'Query',
        'document_pending': 'Document Pending',
        'sro_document_pending': 'SRO Document Pending',
        'positive_subject_tosearch': 'Positive Subject to Search',
        'positive': 'Positive',
        'negative': 'Negative',
    }
    
    context = {
        'is_admin': True,
        'cases': cases,
        'status': status,
        'status_label': status_labels.get(status, status.replace('_', ' ').title()),
        'total_count': cases.count(),
    }
    return render(request, 'accounts/cases_by_filter.html', context)


@login_required
def cases_by_advocate(request, advocate_id):
    """View to show all cases assigned to a specific advocate"""
    user = request.user
    is_admin = user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or user.is_superuser
    if not is_admin:
        messages.error(request, "You don't have access to this page.")
        return redirect('dashboard')
    
    from django.shortcuts import get_object_or_404
    advocate = get_object_or_404(Employee, id=advocate_id, employee_type='advocate')
    
    # Only show parent cases
    cases = Case.objects.filter(assigned_advocate=advocate).select_related('bank', 'branch').order_by('-updated_at')
    
    # Categorize cases
    pending = cases.filter(status__in=['pending', 'draft', 'on_hold', 'on_query', 'query', 'document_pending'])
    completed = cases.filter(status__in=['positive', 'negative', 'positive_subject_tosearch'])
    
    context = {
        'is_admin': True,
        'advocate': advocate,
        'all_cases': cases,
        'pending_cases': pending,
        'completed_cases': completed,
        'total_count': cases.count(),
        'pending_count': pending.count(),
        'completed_count': completed.count(),
    }
    return render(request, 'accounts/cases_by_advocate.html', context)


@login_required
def cases_by_bank(request, bank_id):
    """View to show all cases for a specific bank"""
    user = request.user
    is_admin = user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or user.is_superuser
    if not is_admin:
        messages.error(request, "You don't have access to this page.")
        return redirect('dashboard')
    
    from django.shortcuts import get_object_or_404
    from Bank.models import Bank
    bank = get_object_or_404(Bank, id=bank_id)
    
    # Only show parent cases
    cases = Case.objects.filter(bank=bank).select_related('assigned_advocate', 'branch').order_by('-updated_at')
    
    # Categorize cases
    active = cases.filter(status__in=['pending', 'draft', 'on_hold', 'on_query', 'query', 'document_pending', 'pending_assignment'])
    completed = cases.filter(status__in=['positive', 'negative', 'positive_subject_tosearch'])
    
    context = {
        'is_admin': True,
        'bank': bank,
        'all_cases': cases,
        'active_cases': active,
        'completed_cases': completed,
        'total_count': cases.count(),
        'active_count': active.count(),
        'completed_count': completed.count(),
    }
    return render(request, 'accounts/cases_by_bank.html', context)


@login_required
def generate_mis(request):
    """Generate MIS report as CSV download - excludes address field"""
    user = request.user
    is_admin = user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or user.is_superuser
    
    if not is_admin:
        messages.error(request, "You don't have permission to generate MIS reports.")
        return redirect('dashboard')
    
    # Get all parent cases only
    cases = Case.objects.filter(parent_case__isnull=True).select_related(
        'bank', 'branch', 'case_type', 'assigned_advocate', 'district', 'tehsil'
    ).order_by('-created_at')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="MIS_Report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    # Write header - removed address field
    writer.writerow([
        'Case Number',
        'LRN',
        'Applicant Name',
        'Bank',
        'Branch',
        'Case Type',
        'District',
        'Tehsil',
        'Status',
        'Assigned Advocate',
        'Created Date',
        'Updated Date',
        'Completed Date',
        'Child Cases Count'
    ])
    
    # Write data rows
    for case in cases:
        writer.writerow([
            case.case_number or '',
            case.legal_reference_number or '',
            case.applicant_name or '',
            case.bank.name if case.bank else '',
            case.branch.name if case.branch else '',
            case.case_type.name if case.case_type else '',
            case.district.name if case.district else '',
            case.tehsil.name if case.tehsil else '',
            case.get_status_display(),
            case.assigned_advocate.name if case.assigned_advocate else '',
            case.created_at.strftime('%Y-%m-%d %H:%M') if case.created_at else '',
            case.updated_at.strftime('%Y-%m-%d %H:%M') if case.updated_at else '',
            case.completed_at.strftime('%Y-%m-%d %H:%M') if case.completed_at else '',
            case.child_cases.count()
        ])
    
    return response


@login_required
def super_sro_dashboard(request):
    """Super SRO Dashboard for admins - shows ALL cases that are forwarded to SRO or are PSTS."""
    # Check if user is admin
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists()
    
    if not is_admin:
        messages.error(request, "You don't have permission to access the Super SRO Dashboard.")
        return redirect('dashboard')
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get all SRO-eligible cases (forwarded to SRO or PSTS status)
    # Order by created_at descending to show newest cases first
    eligible_statuses = ['positive', 'positive_subject_tosearch', 'negative']
    sro_cases = Case.objects.filter(
        Q(forwarded_to_sro=True) | Q(status='positive_subject_tosearch'),
        status__in=eligible_statuses
    ).order_by('-created_at')  # Newest first
    
    # Apply search filter if provided
    if search_query:
        sro_cases = sro_cases.filter(
            Q(applicant_name__icontains=search_query) |
            Q(case_number__icontains=search_query) |
            Q(legal_reference_number__icontains=search_query)
        ).distinct()
    
    # Split by status
    sro_pss_cases = sro_cases.filter(status='positive_subject_tosearch')
    sro_negative_cases = sro_cases.filter(status='negative')
    sro_positive_cases = sro_cases.filter(status='positive')
    
    context = {
        "username": user.username,
        "is_admin": True,
        "is_sro": True,
        "sro_all_cases": sro_cases,
        "sro_total_cases": sro_cases.count(),
        "sro_pss_count": sro_pss_cases.count(),
        "sro_negative_count": sro_negative_cases.count(),
        "sro_positive_count": sro_positive_cases.count(),
        "sro_pss_cases": sro_pss_cases,
        "sro_negative_cases": sro_negative_cases,
        "sro_positive_cases": sro_positive_cases,
        "search_query": search_query,
    }
    return render(request, "accounts/sro_dashboard.html", context)
