from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib.auth.decorators import login_required  # retained if needed elsewhere
from django.contrib.auth.models import User  # retained for potential future use
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from django.forms import modelformset_factory
from collections import defaultdict
from django.http import JsonResponse
from django import forms
from django.urls import reverse

from .models import (
	CaseType,
	Employee, Case, CaseUpdate, CaseDocument, State, District, Tehsil
)
from Bank.models import BankBranch, Bank as ExternalBank
from .forms import (
	CaseTypeForm, EmployeeForm, EmployeeEditForm,
	CaseCreationForm, CaseAssignmentForm, CaseDetailsForm, CaseWorkCreateForm, CaseActionForm, CaseDocumentUploadForm,
	QuotationFinalizeForm, SROUpdateForm, StateForm, DistrictForm, TehsilForm, SROScopeForm, ReassignCaseAdvocateForm
)
from .decorators import (
	admin_required, advocate_or_admin_required, sro_or_admin_required,
	get_user_employee, check_case_access
)

# =========================
# BANK CREATION
# =========================
@admin_required
def create_bank(request):
    return redirect('Bank:createbank')

@admin_required
def view_banks(request):
    return redirect('Bank:viewbanks')

@admin_required
def search_banks(request):
    return JsonResponse({'results': [], 'deprecated': True, 'use': 'Bank:viewbanks'})

# =========================
# LOCATION SUGGESTIONS (JSON)
# =========================
def suggest_states(request):
	q = (request.GET.get('q') or '').strip()
	qs = State.objects.all()
	if q:
		qs = qs.filter(name__icontains=q)
	data = [{'id': s.id, 'label': s.name} for s in qs.order_by('name')]
	return JsonResponse({'results': data})

def suggest_districts(request):
	q = (request.GET.get('q') or '').strip()
	state_param = (request.GET.get('state') or '').strip()
	state_name = (request.GET.get('state_name') or '').strip()
	qs = District.objects.select_related('state').all()
	# Filter by state id if numeric, otherwise by state name if provided
	if state_param:
		try:
			qs = qs.filter(state_id=int(state_param))
		except (TypeError, ValueError):
			# Not an int; treat as state name
			qs = qs.filter(state__name__iexact=state_param)
	elif state_name:
		qs = qs.filter(state__name__iexact=state_name)
	if q:
		qs = qs.filter(name__icontains=q)
	data = [{'id': d.id, 'label': f"{d.name} ({d.state.name})"} for d in qs.order_by('name')]
	return JsonResponse({'results': data})

def suggest_tehsils(request):
	q = (request.GET.get('q') or '').strip()
	district_param = (request.GET.get('district') or '').strip()
	district_name = (request.GET.get('district_name') or '').strip()
	state_param = (request.GET.get('state') or '').strip()
	state_name = (request.GET.get('state_name') or '').strip()
	qs = Tehsil.objects.select_related('district', 'district__state').all()
	if district_param:
		try:
			qs = qs.filter(district_id=int(district_param))
		except (TypeError, ValueError):
			qs = qs.filter(district__name__iexact=district_param)
	elif district_name:
		qs = qs.filter(district__name__iexact=district_name)
	elif state_param:
		try:
			qs = qs.filter(district__state_id=int(state_param))
		except (TypeError, ValueError):
			qs = qs.filter(district__state__name__iexact=state_param)
	elif state_name:
		qs = qs.filter(district__state__name__iexact=state_name)
	if q:
		qs = qs.filter(name__icontains=q)
	data = [{'id': t.id, 'label': f"{t.name} ({t.district.name}, {t.district.state.name})"} for t in qs.order_by('name')]
	return JsonResponse({'results': data})

# =========================
# CASE MANAGEMENT
# =========================
@admin_required
def create_case(request):
	if request.method == 'POST':
		form = CaseCreationForm(request.POST)
		if form.is_valid():
			case = form.save(commit=False)
			# Generate number if blank
			if not case.case_number:
				timestamp = timezone.now().strftime('%y%m%d%H%M%S')
				bank_code = case.bank.name[:3].upper()
				case.case_number = f"{bank_code}-{timestamp}"
			# Set status based on quotation / documents
			if form.cleaned_data.get('is_quotation'):
				case.is_quotation = True
				case.status = 'quotation'
				case.quotation_price = form.cleaned_data.get('quotation_price')
				case.documents_present = False
				case.assigned_advocate = None
			else:
				# Not a quotation
				docs = form.cleaned_data.get('documents_present')
				ass_adv = form.cleaned_data.get('assigned_advocate')
				assign_to_admin = request.POST.get('assign_to_admin') in ['on','true','True','1']
				if assign_to_admin:
					case.status = 'pending'
					# Ensure current user has an Employee profile or create a generic Admin employee
					admin_user = request.user
					admin_emp = getattr(admin_user, 'employee', None)
					if not admin_emp:
						# Create minimal employee record for admin if missing
						emp_name = getattr(admin_user, 'get_full_name', lambda: '')() or admin_user.username or 'Admin'
						emp_email = admin_user.email or f"admin_{admin_user.id}@example.com"
						# Generate unique employee_id
						base_emp_id = f"ADMIN-{admin_user.id}"
						from .models import Employee
						if Employee.objects.filter(employee_id=base_emp_id).exists():
							base_emp_id = f"ADMIN-{admin_user.id}-{timezone.now().strftime('%H%M%S')}"
						admin_emp = Employee.objects.create(
							user=admin_user,
							name=emp_name,
							employee_id=base_emp_id,
							mobile='-',
							email=emp_email,
							employee_type='advocate',  # allow doing case work
							initials='AD',
							is_active=True,
						)
					else:
						# Ensure initials are set to AD for admin case work preference
						if not admin_emp.initials or admin_emp.initials.upper() != 'AD':
							admin_emp.initials = 'AD'
							admin_emp.save(update_fields=['initials'])
					case.assigned_advocate = admin_emp
				elif docs and ass_adv:
					case.status = 'pending'
				else:
					case.status = 'pending_assignment'
			case.save()
			# Log creation event
			try:
				if case.is_quotation or case.status == 'quotation':
					remark_msg = f"Created as quotation. Quoted price={case.quotation_price}"
				elif case.assigned_advocate:
					remark_msg = f"Created and assigned to {case.assigned_advocate.name}"
				else:
					remark_msg = "Created and queued for assignment"
				CaseUpdate.objects.create(case=case, action='created', remark=remark_msg)
			except Exception:
				pass
			if case.status == 'quotation':
				messages.success(request, f"Quotation case {case.case_number} created with quoted price {case.quotation_price}.")
			elif case.assigned_advocate:
				messages.success(request, f"Case {case.case_number} created and assigned to {case.assigned_advocate.name}.")
			else:
				messages.success(request, f"Case {case.case_number} created and queued for assignment.")
			# Redirect back to create page for rapid entry
			return redirect('create_case')
	else:
		form = CaseCreationForm()
	return render(request, 'cases/create_case.html', {'form': form})


@advocate_or_admin_required
def view_cases(request):
	employee = get_user_employee(request.user)
	is_admin = request.user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or request.user.is_superuser

	search_query = request.GET.get('search', '').strip()
	completed_search = request.GET.get('completed_search', '').strip()
	# Admins: show only parent cases to keep list concise; Advocates: show PARENT cases only (children shown inside parent detail)
	base_admin_qs = Case.objects.select_related('bank', 'case_type', 'assigned_advocate').filter(parent_case__isnull=True)
	if is_admin:
		if search_query:
			# Search across parent fields and child fields, but return distinct parents only
			cases_qs = base_admin_qs.filter(
				Q(applicant_name__icontains=search_query) |
				Q(case_number__icontains=search_query) |
				Q(legal_reference_number__icontains=search_query) |
				Q(child_cases__applicant_name__icontains=search_query) |
				Q(child_cases__case_number__icontains=search_query) |
				Q(child_cases__legal_reference_number__icontains=search_query)
			).distinct()
		else:
			cases_qs = base_admin_qs
		cases = cases_qs.order_by('-created_at')
	elif employee and employee.employee_type == 'advocate':
		# Advocate view: show only PARENT cases; child cases are displayed within parent detail
		qs = Case.objects.select_related('bank', 'case_type', 'assigned_advocate').filter(
			assigned_advocate=employee,
			parent_case__isnull=True
		).order_by('-updated_at')
		active_statuses = ['pending','draft','on_hold','on_query','query','document_pending','sro_document_pending']
		completed_statuses = ['positive','positive_subject_tosearch','negative']
		today = timezone.localdate()
		pending_all = qs.filter(status__in=active_statuses)
		# Reassigned tray: cases recently reassigned (most recent first)
		# Reassigned tray: cases recently reassigned (last 7 days), exclude finalized
		cutoff = timezone.now() - timedelta(days=7)
		reassigned_cases = qs.filter(
			reassigned_at__gte=cutoff
		).exclude(status__in=['positive','positive_subject_tosearch','negative']).order_by('-reassigned_at')[:50]
		# Build Pending Today/Overall and include reassigned (we will mark with a badge in UI)
		reassigned_ids = list(reassigned_cases.values_list('id', flat=True))
		pending_today = pending_all.filter(updated_at__date=today)
		pending_overall = pending_all.exclude(id__in=pending_today.values('id'))
		completed_results = []
		if completed_search:
			completed_results = qs.filter(status__in=completed_statuses).filter(
				Q(applicant_name__icontains=completed_search) |
				Q(case_number__icontains=completed_search) |
				Q(legal_reference_number__icontains=completed_search)
			).order_by('-updated_at')
		# Keep cases for status counts, but primary rendering uses pending_today/pending_overall
		cases = qs
	else:
		cases = Case.objects.none()

	quotation_buckets = [('Quotation', 'quotation', 'gray')]
	pending_assignment_buckets = [('Pending Assignment', 'pending_assignment', 'orange')]
	pending_buckets = [('Pending', 'pending', 'purple')]
	active_buckets = [
		('On Hold', 'on_hold', 'blue'),
		('On Query', 'on_query', 'yellow'),
		('Query', 'query', 'yellow'),
		('Document Pending', 'document_pending', 'indigo'),
		('SRO Document Pending', 'sro_document_pending', 'cyan'),
	]
	draft_buckets = [('Draft', 'draft', 'gray')]
	completed_positive_buckets = [('Positive', 'positive', 'emerald')]
	completed_negative_buckets = [('Negative', 'negative', 'red')]

	all_buckets = draft_buckets + quotation_buckets + pending_assignment_buckets + pending_buckets + active_buckets + completed_positive_buckets + completed_negative_buckets
	status_counts = {s: 0 for s in [b[1] for b in all_buckets]}
	for c in cases:
		if c.status in status_counts:
			status_counts[c.status] += 1

	context = {
		'cases': cases,
		'quotation_buckets': quotation_buckets,
		'pending_assignment_buckets': pending_assignment_buckets,
		'pending_buckets': pending_buckets,
		'draft_buckets': draft_buckets,
		'active_buckets': active_buckets,
		'completed_positive_buckets': completed_positive_buckets,
		'completed_negative_buckets': completed_negative_buckets,
		'status_counts': status_counts,
		'is_admin': is_admin,
		'search_query': search_query,
	}
	# Advocate-specific context additions
	if not is_admin and employee and employee.employee_type == 'advocate':
		context.update({
			'pending_today': pending_today,
			'pending_overall': pending_overall,
			'reassigned_cases': reassigned_cases,
			'reassigned_ids': reassigned_ids,
			'completed_results': completed_results,
			'completed_search_query': completed_search,
		})
	return render(request, 'cases/view_cases.html', context)


@advocate_or_admin_required
def advocate_cases_filtered(request, filter_type):
	employee = get_user_employee(request.user)
	is_admin = request.user.groups.filter(name__in=['ADMIN','CO-ADMIN']).exists() or request.user.is_superuser
	# Only parent cases in filtered listings
	# Admin: parent-only; Advocates: all their assigned cases
	qs = Case.objects.all()
	title = 'All Cases'
	if employee and employee.employee_type == 'advocate' and not is_admin:
		qs = qs.filter(assigned_advocate=employee)
	elif is_admin:
		qs = qs.filter(parent_case__isnull=True)
	status_map = {
		'active': ['on_hold','on_query','query','document_pending','sro_document_pending'],
		'pending': ['pending'],
		'pending_assignment': ['pending_assignment'],
		'quotation': ['quotation'],
		'document_pending': ['document_pending'],
		'sro_document_pending': ['sro_document_pending'],
		'hold': ['on_hold'],
		'doc_hold': ['document_pending','sro_document_pending'],
		'completed': ['positive','negative','positive_subject_tosearch'],
		'hold_query_doc': ['on_hold','on_query','query','document_pending','sro_document_pending'],
		'all': ['draft','quotation','pending_assignment','pending','document_pending','sro_document_pending','on_hold','on_query','query','positive','negative','positive_subject_tosearch']
	}
	if filter_type in status_map:
		qs = qs.filter(status__in=status_map[filter_type])
		title = filter_type.replace('_',' ').title() + ' Cases'
	cases = qs.select_related('bank','case_type','assigned_advocate').order_by('-updated_at')

	quotation_buckets = [('Quotation', 'quotation', 'gray')]
	pending_assignment_buckets = [('Pending Assignment', 'pending_assignment', 'orange')]
	pending_buckets = [('Pending', 'pending', 'purple')]
	active_buckets = [
		('On Hold', 'on_hold', 'blue'),
		('On Query', 'on_query', 'yellow'),
		('Query', 'query', 'yellow'),
		('Document Pending', 'document_pending', 'indigo'),
		('SRO Document Pending', 'sro_document_pending', 'cyan'),
	]
	draft_buckets = [('Draft', 'draft', 'gray')]
	completed_positive_buckets = [('Positive', 'positive', 'emerald')]
	completed_negative_buckets = [('Negative', 'negative', 'red')]

	all_buckets = draft_buckets + quotation_buckets + pending_assignment_buckets + pending_buckets + active_buckets + completed_positive_buckets + completed_negative_buckets
	status_counts = {s: 0 for s in [b[1] for b in all_buckets]}
	for c in cases:
		if c.status in status_counts:
			status_counts[c.status] += 1

	context = {
		'cases': cases,
		'list_title': title,
		'quotation_buckets': quotation_buckets,
		'pending_assignment_buckets': pending_assignment_buckets,
		'pending_buckets': pending_buckets,
		'draft_buckets': draft_buckets,
		'active_buckets': active_buckets,
		'completed_positive_buckets': completed_positive_buckets,
		'completed_negative_buckets': completed_negative_buckets,
		'status_counts': status_counts,
		'is_admin': is_admin,
	}

	# Add advocate-specific context for view_cases template
	if not is_admin and employee and employee.employee_type == 'advocate':
		today = timezone.localdate()
		pending_all = cases.filter(status='pending')
		pending_today = pending_all.filter(updated_at__date=today)
		pending_overall = pending_all.exclude(id__in=pending_today.values('id'))
		
		# Reassigned cases in last 7 days
		cutoff = timezone.now() - timedelta(days=7)
		reassigned_cases = qs.filter(reassigned_at__gte=cutoff).exclude(status__in=['positive','positive_subject_tosearch','negative']).order_by('-reassigned_at')[:50]
		reassigned_ids = list(reassigned_cases.values_list('id', flat=True))
		
		context.update({
			'pending_today': pending_today,
			'pending_overall': pending_overall,
			'reassigned_cases': reassigned_cases,
			'reassigned_ids': reassigned_ids,
		})

	return render(request, 'cases/view_cases.html', context)

@admin_required
def finalize_quotation(request, case_id):
	"""Convert a quotation case into a regular case by confirming price, documents, and assigning advocate."""
	case = get_object_or_404(Case, id=case_id)
	if case.status != 'quotation' or not case.is_quotation:
		messages.error(request, 'This case is not in quotation stage.')
		return redirect('case_detail', case_id=case.id)

	if request.method == 'POST':
		form = QuotationFinalizeForm(request.POST, instance=case)
		if form.is_valid():
			case = form.save(commit=False)
			case.is_quotation = False
			case.quotation_finalized = True
			case.status = 'pending'  # moves to pending since assigned advocate present
			case.save()
			# Ensure child cases mirror parent status
			try:
				case.propagate_status_to_children()
			except Exception:
				pass
			# Log finalize event
			try:
				adv = case.assigned_advocate.name if case.assigned_advocate else '-'
				CaseUpdate.objects.create(
					case=case,
					action='quotation_finalized',
					remark=f"Final price={case.quotation_price}; Assigned advocate={adv}"
				)
			except Exception:
				pass
			messages.success(request, f'Quotation finalized and case {case.case_number} assigned to {case.assigned_advocate.name}.')
			return redirect('case_detail', case_id=case.id)
	else:
		form = QuotationFinalizeForm(instance=case, initial={
			'quotation_price': case.quotation_price
		})
	return render(request, 'cases/finalize_quotation.html', {'form': form, 'case': case})


@admin_required
def view_pending_cases(request):
	pending_cases = Case.objects.filter(
		parent_case__isnull=True,
		status__in=['pending_assignment', 'document_pending', 'sro_document_pending']
	).select_related('bank','case_type','assigned_advocate').order_by('-created_at')
	return render(request, 'cases/view_pending_cases.html', {'cases': pending_cases})


@admin_required
def assign_case_advocate(request, case_id):
	case = get_object_or_404(Case, id=case_id)
	if request.method == 'POST':
		form = CaseAssignmentForm(request.POST, instance=case)
		if form.is_valid():
			case = form.save(commit=False)
			case.status = 'pending'
			case.save()
			# Ensure child cases mirror parent status
			try:
				case.propagate_status_to_children()
			except Exception:
				pass
			# Log assignment
			try:
				advocate_name = case.assigned_advocate.name if case.assigned_advocate else '-' 
				CaseUpdate.objects.create(case=case, action='assigned', remark=f"Assigned to {advocate_name}")
			except Exception:
				pass
			messages.success(request, f"Case {case.case_number} assigned to {case.assigned_advocate.name}.")
			return redirect('view_pending_cases')
	else:
		form = CaseAssignmentForm(instance=case)
	return render(request, 'cases/assign_case_advocate.html', {'form': form, 'case': case})


@admin_required
def reassign_case_advocate(request, case_id):
	"""Admin can reassign advocate on any case (even finalized), optionally cascading to children.
	Optionally mark case back to 'pending' to reflect new work has arrived.
	"""
	case = get_object_or_404(Case, id=case_id)
	
	# If trying to reassign a child case, redirect to parent
	if case.parent_case:
		messages.info(request, f"Reassigning advocates for child cases is done through the parent case.")
		return redirect('reassign_case_advocate', case_id=case.parent_case.id)
	
	old_advocate_id = case.assigned_advocate_id
	if request.method == 'POST':
		form = ReassignCaseAdvocateForm(request.POST, instance=case)
		if form.is_valid():
			new_adv = form.cleaned_data['assigned_advocate']
			# Update parent
			case.assigned_advocate = new_adv
			# Mark reassigned timestamp
			case.reassigned_at = timezone.now()
			case.save()
			# Always cascade to children
			for child in case.child_cases.all():
				child.assigned_advocate = new_adv
				child.reassigned_at = timezone.now()
				child.save()
			# Log update
			try:
				who = getattr(new_adv, 'name', '-') if new_adv else '-'
				remark = f"Reassigned advocate to {who} at {timezone.now().strftime('%Y-%m-%d %H:%M')} (status preserved: {case.status}); cascaded to all children"
				if old_advocate_id and old_advocate_id != getattr(new_adv,'id',None):
					remark += f"; removed from old advocate id={old_advocate_id}"
				CaseUpdate.objects.create(case=case, action='reassigned', remark=remark)
			except Exception:
				pass
			messages.success(request, 'Advocate reassigned successfully.')
			return redirect('case_detail', case_id=case.id)
	else:
		form = ReassignCaseAdvocateForm(instance=case)
	return render(request, 'cases/reassign_case_advocate.html', {'form': form, 'case': case})


@advocate_or_admin_required
def case_detail(request, case_id):
	case = get_object_or_404(Case, id=case_id)
	
	# If this is a child case, redirect to parent case detail
	if case.parent_case:
		messages.info(request, f"Viewing parent case. The requested case ({case.case_number}) is a linked property case shown below.")
		return redirect('case_detail', case_id=case.parent_case.id)
	
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to view this case.")
		return redirect('view_cases')
	# Role flag for template logic (e.g., hiding receipt amount for employees)
	is_admin = request.user.is_superuser or request.user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists()
	
	# Check if user is SRO
	is_sro = False
	try:
		employee = get_user_employee(request.user)
		if employee and employee.employee_type == 'sro' and not is_admin:
			is_sro = True
	except Exception:
		pass
	
	# Fetch all updates for this case, ordered by update_date
	updates = CaseUpdate.objects.filter(case=case).order_by('update_date')
	# Split documents into receipt vs final. Prefer explicit flag; fallback to description hints for legacy rows.
	docs = list(case.documents.all())
	receipt_docs = []
	final_docs = []
	for d in docs:
		if getattr(d, 'is_receipt', None) is True:
			receipt_docs.append(d)
		elif getattr(d, 'is_receipt', None) is False:
			final_docs.append(d)
		else:
			desc = (getattr(d, 'description', '') or '').lower()
			if 'receipt' in desc:
				receipt_docs.append(d)
			else:
				final_docs.append(d)
	# Order lists: show latest receipt first; final docs chronological
	try:
		receipt_docs.sort(key=lambda x: x.uploaded_at or 0, reverse=True)
	except Exception:
		pass
	try:
		final_docs.sort(key=lambda x: x.uploaded_at or 0)
	except Exception:
		pass
	# Compute top-level parent (root) for consistent child-add linking
	root_case = case
	while getattr(root_case, 'parent_case_id', None):
		root_case = root_case.parent_case
	# Determine if core details are complete to drive merged Work/Action button
	details_complete = False
	try:
		if hasattr(case, 'has_complete_details'):
			details_complete = bool(case.has_complete_details())
		else:
			# Fallback: check key fields presence
			details_complete = all([
				bool(case.property_address), bool(case.state), bool(case.district), bool(case.tehsil), bool(case.branch_id)
			])
	except Exception:
		pass
	# Finalization lock flag
	is_finalized = False
	try:
		if hasattr(case, 'is_final_status'):
			is_finalized = bool(case.is_final_status())
		else:
			is_finalized = case.status in ['positive','negative','positive_subject_tosearch']
	except Exception:
		pass
	# Active quotation flag (not yet finalized)
	is_active_quotation = False
	try:
		is_active_quotation = (case.status == 'quotation' and bool(getattr(case, 'is_quotation', False)) and not bool(getattr(case, 'quotation_finalized', False)))
	except Exception:
		pass
	return render(request, 'cases/case_detail.html', {
		'case': case,
		'updates': updates,
		'root_case': root_case,
		'receipt_docs': receipt_docs,
		'final_docs': final_docs,
		'details_complete': details_complete,
		'is_finalized': is_finalized,
		'is_active_quotation': is_active_quotation,
		'is_admin': is_admin,
		'is_sro': is_sro,
	})


def sro_case_detail(request, case_id):
	"""SRO-specific case detail view with orange theme."""
	case = get_object_or_404(Case, id=case_id)
	
	# If this is a child case, redirect to parent case detail
	if case.parent_case:
		messages.info(request, f"Viewing parent case. The requested case ({case.case_number}) is a linked property case shown below.")
		return redirect('sro_case_detail', case_id=case.parent_case.id)
	
	# Verify user is SRO
	try:
		employee = get_user_employee(request.user)
		if not employee or employee.employee_type != 'sro':
			messages.error(request, "Access denied. This page is only for SRO users.")
			return redirect('dashboard')
	except Exception:
		messages.error(request, "Access denied.")
		return redirect('dashboard')
	
	# Check if case is in SRO's allowed districts
	if case.district and employee.allowed_districts.exists():
		if not employee.allowed_districts.filter(id=case.district.id).exists():
			messages.error(request, "You don't have permission to view this case (district restriction).")
			return redirect('sro_dashboard')
	
	# Fetch all updates for this case
	updates = CaseUpdate.objects.filter(case=case).order_by('update_date')
	
	# Split documents into receipt vs final
	docs = list(case.documents.all())
	receipt_docs = []
	final_docs = []
	for d in docs:
		if getattr(d, 'is_receipt', None) is True:
			receipt_docs.append(d)
		elif getattr(d, 'is_receipt', None) is False:
			final_docs.append(d)
		else:
			desc = (getattr(d, 'description', '') or '').lower()
			if 'receipt' in desc:
				receipt_docs.append(d)
			else:
				final_docs.append(d)
	
	# Order lists
	try:
		receipt_docs.sort(key=lambda x: x.uploaded_at or 0, reverse=True)
		final_docs.sort(key=lambda x: x.uploaded_at or 0)
	except Exception:
		pass
	
	# Compute root case
	root_case = case
	while getattr(root_case, 'parent_case_id', None):
		root_case = root_case.parent_case
	
	return render(request, 'cases/case_detail.html', {
		'case': case,
		'updates': updates,
		'root_case': root_case,
		'receipt_docs': receipt_docs,
		'final_docs': final_docs,
		'details_complete': False,
		'is_finalized': False,
		'is_active_quotation': False,
		'is_admin': False,
		'is_sro': True,
	})


@advocate_or_admin_required
def add_case_work(request, case_id):
	"""Attach an additional work (case type) to a case with a required document upload."""
	case = get_object_or_404(Case, id=case_id)
	# Disallow adding new work if case is finalized
	if hasattr(case, 'is_final_status') and case.is_final_status():
		messages.error(request, 'This case is closed. New work cannot be added after finalization. You can still replace the final document.')
		return redirect('case_detail', case_id=case.id)
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to edit this case.")
		return redirect('view_cases')
	if request.method == 'POST':
		form = CaseWorkCreateForm(request.POST, request.FILES)
		# Restrict selectable case types to those configured for this case's bank
		valid_types = CaseType.objects.filter(bank_case_types__bank=case.bank).distinct()
		used_type_ids = [case.case_type_id] + list(case.works.values_list('case_type_id', flat=True))
		form.fields['case_type'].queryset = valid_types.exclude(id__in=used_type_ids).order_by('name')
		if form.is_valid():
			work = form.save(commit=False)
			work.case = case
			work.save()
			messages.success(request, 'Work added to case.')
			return redirect('case_detail', case_id=case.id)
	else:
		form = CaseWorkCreateForm()
		valid_types = CaseType.objects.filter(bank_case_types__bank=case.bank).distinct()
		used_type_ids = [case.case_type_id] + list(case.works.values_list('case_type_id', flat=True))
		form.fields['case_type'].queryset = valid_types.exclude(id__in=used_type_ids).order_by('name')
	return render(request, 'cases/add_case_work.html', {'form': form, 'case': case})


@advocate_or_admin_required
def work_on_case(request, case_id):
	case = get_object_or_404(Case, id=case_id)
	
	# If this is a child case, redirect to parent case
	if case.parent_case:
		messages.warning(request, f"Cannot work on child case directly. Redirecting to parent case.")
		return redirect('work_on_case', case_id=case.parent_case.id)
	
	# Lock editing if case finalized
	if hasattr(case, 'is_final_status') and case.is_final_status():
		messages.error(request, 'Case is finalized. Details can no longer be edited. You may replace the final document if needed.')
		return redirect('case_detail', case_id=case.id)
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to edit this case.")
		return redirect('view_cases')

	# Safety: if existing branch FK points to a non-existent BankBranch (from legacy data),
	# clear it in-memory before binding the form to avoid FK violations on save.
	try:
		if getattr(case, 'branch_id', None) and not BankBranch.objects.filter(pk=case.branch_id).exists():
			case.branch = None  # do NOT save yet; just clear the in-memory relation
	except Exception:
		pass

	if request.method == 'POST':
		# Capture original values to log diffs
		original = {
			'property_address': case.property_address,
			'state': case.state,
			'district': case.district,
			'tehsil': case.tehsil,
			'branch': case.branch_id,
		}
		form = CaseDetailsForm(request.POST, instance=case)
		# Attach posted state before cleaning to narrow branch queryset if needed
		posted_state = (request.POST.get('state') or '').strip()
		if posted_state:
			case.state = posted_state  # temp assign for form logic
		if form.is_valid():
			# Duplicate check flow for school cases
			is_school_case = form.cleaned_data.get('is_school_case')
			save_anyway = request.POST.get('save_anyway') == '1'
			duplicate_cases = []
			if is_school_case and not save_anyway:
				# Search for duplicates matching applicant_name, tehsil, district (case-insensitive), excluding current case
				aname = (case.applicant_name or '').strip()
				tehsil = (form.cleaned_data.get('tehsil') or '').strip()
				district = (form.cleaned_data.get('district') or '').strip()
				if aname and (tehsil or district):
					duplicate_cases = list(Case.objects.filter(
						is_school_case=True
					).filter(
						Q(applicant_name__iexact=aname)
					).filter(
						Q(tehsil__iexact=tehsil) if tehsil else Q()
					).filter(
						Q(district__iexact=district) if district else Q()
					).exclude(id=case.id)[:10])
				if duplicate_cases:
					# Show the page with duplicates modal; don't save yet
					return render(request, 'cases/work_on_case.html', {
						'form': form,
						'case': case,
						'duplicate_cases': duplicate_cases,
					})

			# Guard against legacy FK issues: if the selected/initial branch somehow
			# doesn't exist at commit time, surface a form error instead of crashing.
			try:
				updated = form.save()
			except Exception as e:
				from django.db import IntegrityError, transaction
				if isinstance(e, IntegrityError) or 'FOREIGN KEY constraint' in str(e):
					# Diagnose which FK is actually missing to show a precise message
					sel_branch = form.cleaned_data.get('branch')
					branch_ok = bool(sel_branch and BankBranch.objects.filter(pk=getattr(sel_branch, 'pk', None)).exists())
					bank_ok = ExternalBank.objects.filter(pk=case.bank_id).exists()
					ctype_ok = CaseType.objects.filter(pk=case.case_type_id).exists()
					adv_ok = True
					try:
						adv_ok = (case.assigned_advocate_id is None) or Employee.objects.filter(pk=case.assigned_advocate_id).exists()
					except Exception:
						adv_ok = True
					employee_ok = True
					try:
						employee_ok = (case.employee_id is None) or Employee.objects.filter(pk=case.employee_id).exists()
					except Exception:
						employee_ok = True
					parent_ok = True
					try:
						parent_ok = (case.parent_case_id is None) or Case.objects.filter(pk=case.parent_case_id).exists()
					except Exception:
						parent_ok = True
					# Attempt automatic repair for nullable FKs if they are the root cause
					repaired = False
					if employee_ok is False or adv_ok is False or parent_ok is False:
						try:
							with transaction.atomic():
								if employee_ok is False:
									case.employee = None
								if adv_ok is False:
									case.assigned_advocate = None
								if parent_ok is False:
									case.parent_case = None
								# Do not auto-heal missing bank/case_type/branch
								case.save()
								repaired = True
						except Exception:
							repaired = False
					if repaired:
						messages.info(request, 'Stale references were repaired automatically. Please re-apply your change if needed.')
						updated = case  # treat as updated
					else:
						if not branch_ok:
							form.add_error('branch', 'Selected branch no longer exists. Please choose a valid branch.')
						elif not bank_ok:
							form.add_error(None, 'Selected bank is invalid. Please re-open the case or contact admin to fix this case\'s bank reference.')
						elif not ctype_ok:
							form.add_error(None, 'Case Type linked to this case is missing. Please contact admin to re-create or reassign the case type.')
						elif not adv_ok:
							form.add_error(None, 'The assigned advocate record is missing. Please reassign the case to a valid advocate.')
						elif not employee_ok:
							form.add_error(None, 'The internal employee reference is missing. It has to be cleared by admin.')
						elif not parent_ok:
							form.add_error(None, 'Parent case reference is invalid. Please reload and try again or contact admin.')
						else:
							form.add_error(None, 'A database constraint failed while saving. Please recheck fields and try again.')
					# Add an admin-only hint with IDs for quick triage
					try:
						if request.user.is_superuser:
							messages.warning(request, f"FK diag: branch_ok={branch_ok}, bank={case.bank_id}, case_type={case.case_type_id}, adv={case.assigned_advocate_id}, employee={case.employee_id}, parent={case.parent_case_id}")
					except Exception:
						pass
					return render(request, 'cases/work_on_case.html', {'form': form, 'case': case})
				raise
			# Ensure the flag persisted (handled in form.save but kept for clarity)
			if is_school_case != updated.is_school_case:
				updated.is_school_case = bool(is_school_case)
				updated.save(update_fields=['is_school_case'])
			# Compute diffs
			diffs = []
			if original['property_address'] != updated.property_address:
				diffs.append('property_address')
			if original['state'] != updated.state:
				diffs.append('state')
			if original['district'] != updated.district:
				diffs.append('district')
			if original['tehsil'] != updated.tehsil:
				diffs.append('tehsil')
			if original['branch'] != (updated.branch_id if updated.branch_id else None):
				diffs.append('branch')
			if diffs:
				try:
					# Build a compact remark showing new values for changed fields
					parts = []
					if 'property_address' in diffs:
						parts.append('address updated')
					if 'state' in diffs:
						parts.append(f"state={updated.state}")
					if 'district' in diffs:
						parts.append(f"district={updated.district}")
					if 'tehsil' in diffs:
						parts.append(f"tehsil={updated.tehsil}")
					if 'branch' in diffs:
						parts.append(f"branch_id={updated.branch_id}")
					CaseUpdate.objects.create(case=case, action='work_update', remark='; '.join(parts))
				except Exception:
					pass
			messages.success(request, 'Case details updated. Proceed to take action.')
			return redirect('case_action', case_id=case.id)
	else:
		form = CaseDetailsForm(instance=case)

	return render(request, 'cases/work_on_case.html', {'form': form, 'case': case})


@advocate_or_admin_required
def case_action(request, case_id):
	"""Handle case action workflow including finalization, additional property creation, and document upload."""
	case = get_object_or_404(Case, id=case_id)
	
	# If this is a child case, redirect to parent case
	if case.parent_case:
		messages.warning(request, f"Cannot take action on child case directly. Redirecting to parent case.")
		return redirect('case_action', case_id=case.parent_case.id)
	
	# Disallow taking action if the case is already finalized
	if hasattr(case, 'is_final_status') and case.is_final_status():
		messages.info(request, 'This case is already finalized. You can upload/replace the final document from the case page.')
		return redirect('case_detail', case_id=case.id)
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to act on this case.")
		return redirect('view_cases')

	if request.method == 'POST':
		form = CaseActionForm(request.POST, case=case)
		if form.is_valid():
			action = form.cleaned_data['action']
			remark = form.cleaned_data.get('remark')
			forward = form.cleaned_data.get('forward_to_sro', False)

			# Additional property creation moved to a dedicated step post-finalization

			# Enforce: final actions require that core work fields are completed
			if action in ['positive', 'positive_subject_tosearch', 'negative'] and not case.has_complete_details():
				messages.error(request, 'Please complete case details (Address, State, District, Tehsil, Branch) before finalizing.')
				return redirect('work_on_case', case_id=case.id)

			# Map actions to statuses (on_hold removed from this form; handled separately)
			if action == 'positive_subject_tosearch':
				case.status = 'positive_subject_tosearch'
				case.forwarded_to_sro = True  # auto forwardonl
				case.completed_at = timezone.now()
				case.generate_legal_reference_number()
			elif action == 'positive':
				case.status = 'positive'
				case.completed_at = timezone.now()
				case.generate_legal_reference_number()
				if forward:
					case.forwarded_to_sro = True
			elif action == 'negative':
				case.status = 'negative'
				case.completed_at = timezone.now()
				case.generate_legal_reference_number()
				if forward:
					case.forwarded_to_sro = True
			elif action == 'draft':
				case.status = 'draft'
				case.forwarded_to_sro = False
				case.completed_at = None
			elif action == 'query':
				case.status = 'query'
				case.forwarded_to_sro = False
				case.completed_at = None
			else:
				messages.error(request, 'Invalid action selected.')
				return redirect('case_action', case_id=case.id)

			case.save()
			# If a child case was forwarded, ensure the root parent is also flagged for SRO when appropriate
			if case.forwarded_to_sro:
				root = case
				while getattr(root, 'parent_case_id', None):
					root = root.parent_case
				# Only set forwarded flag on parent if it is in a final status
				if root and root.parent_case is None and root.status in ['positive', 'positive_subject_tosearch', 'negative'] and not root.forwarded_to_sro:
					root.forwarded_to_sro = True
					root.save(update_fields=['forwarded_to_sro'])
			# Ensure child cases mirror parent status
			try:
				case.propagate_status_to_children()
			except Exception:
				pass
			CaseUpdate.objects.create(case=case, action=action, remark=remark)
			messages.success(request, f'Case updated to {case.get_status_display()}')
			# For final statuses, redirect to mandatory document upload step
			if case.status in ['positive', 'positive_subject_tosearch', 'negative']:
				# If there are child cases, redirect to group upload so each case can upload its own document
				if case.child_cases.exists():
					return redirect('case_upload_documents_group', case_id=case.id)
				return redirect('case_upload_document', case_id=case.id)
			return redirect('case_detail', case_id=case.id)
	else:
		form = CaseActionForm(case=case)
	return render(request, 'cases/case_action.html', {'form': form, 'case': case})



@advocate_or_admin_required
def case_put_on_hold(request, case_id):
	"""Set a case to on_hold status from Actions sidebar. Requires POST to execute."""
	case = get_object_or_404(Case, id=case_id)
	if hasattr(case, 'is_final_status') and case.is_final_status():
		messages.error(request, 'Finalized cases cannot be placed on hold.')
		return redirect('case_detail', case_id=case.id)
	# Only allow on-hold for early lifecycle statuses per policy
	allowed_statuses = ['pending_assignment', 'pending', 'on_query', 'query']
	if case.status not in allowed_statuses and case.status != 'on_hold':
		messages.error(request, 'Putting on hold is only allowed before substantial work (Pending Assignment / Pending / On Query).')
		return redirect('case_detail', case_id=case.id)
	if case.status == 'on_hold':
		messages.info(request, 'Case is already on hold.')
		return redirect('case_detail', case_id=case.id)
	if request.method == 'POST':
		remark = request.POST.get('remark', '').strip() or 'Placed on hold from Actions sidebar.'
		case.status = 'on_hold'
		case.save(update_fields=['status'])
		CaseUpdate.objects.create(case=case, action='on_hold', remark=remark)
		messages.success(request, 'Case placed on hold.')
	return redirect('case_detail', case_id=case.id)


@advocate_or_admin_required
def case_upload_document(request, case_id):
	"""Mandatory step after finalization to upload supporting document. Shows the LRN and enforces single-document policy."""
	case = get_object_or_404(Case, id=case_id)
	
	# Allow child case uploads when coming from add_child_case flow (parent is finalized)
	# Only redirect if trying to access independently (not from creation flow)
	parent_case = None
	if case.parent_case:
		parent_case = case.parent_case
		# Check if this is fresh from creation (has LRN but no document yet)
		if case.legal_reference_number and not case.documents.exists():
			# Allow upload for this child case
			pass
		else:
			messages.warning(request, f"Cannot upload document for child case directly. Redirecting to parent case.")
			return redirect('case_upload_document', case_id=case.parent_case.id)
	
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to upload for this case.")
		return redirect('view_cases')
	# Allow upload after SRO receipt when returned to advocate
	if case.status not in ['positive', 'positive_subject_tosearch', 'negative', 'document_pending', 'sro_document_pending']:
		messages.info(request, 'Document upload is only required after SRO receipt or after finalizing the case.')
		return redirect('case_detail', case_id=case.id)
	# Ensure LRN exists
	if not case.legal_reference_number:
		case.generate_legal_reference_number(); case.save()

	if request.method == 'POST':
		form = CaseDocumentUploadForm(request.POST, request.FILES)
		if form.is_valid():
			file = form.files['supporting_document']
			desc = form.cleaned_data.get('document_description') or f"Final document for {case.get_status_display()}"
			# Replace only prior final docs (non-receipt); preserve receipts
			prior_finals = list(case.documents.filter(is_receipt=False))
			if prior_finals:
				for d in prior_finals:
					try:
						if d.file:
							d.file.delete(save=False)
					except Exception:
						pass
					d.delete()
				CaseUpdate.objects.create(case=case, action='document_replaced', remark='Replaced after finalization upload.')
			else:
				CaseUpdate.objects.create(case=case, action='document_uploaded', remark='Uploaded after finalization.')
			CaseDocument.objects.create(
				case=case,
				file=file,
				uploaded_by=getattr(request.user, 'employee', None) if request.user.is_authenticated else None,
				description=desc,
				is_receipt=False
			)
			messages.success(request, 'Supporting document uploaded successfully.')
			# If the case is not finalized yet (document pending), send advocate to action page to finalize now
			if case.status in ['document_pending','sro_document_pending']:
				return redirect('case_action', case_id=case.id)
			return redirect('post_finalize_options', case_id=case.id)
	else:
		form = CaseDocumentUploadForm()
	return render(request, 'cases/case_upload_document.html', {'case': case, 'form': form})


@advocate_or_admin_required
def case_upload_documents_group(request, case_id):
	"""Upload required documents for a parent case and all its subcases in one page.
	Each case requires an individual document; enforce single-document policy per case.
	"""
	parent = get_object_or_404(Case, id=case_id)
	if not check_case_access(request.user, parent):
		messages.error(request, "You don't have permission to upload for this case.")
		return redirect('view_cases')
	# Only allow when parent is in a final status
	if parent.status not in ['positive', 'positive_subject_tosearch', 'negative']:
		messages.info(request, 'Group upload is only available after finalizing the parent case.')
		return redirect('case_detail', case_id=parent.id)
	# Ensure LRNs exist
	changed = False
	if not parent.legal_reference_number:
		parent.generate_legal_reference_number(); changed = True
	children = list(parent.child_cases.all())
	for c in children:
		if not c.legal_reference_number:
			c.generate_legal_reference_number(); c.save()
	if changed:
		parent.save()

	if request.method == 'POST':
		# Expect files named like doc_<case_id> and optional description desc_<case_id>
		uploader = getattr(request.user, 'employee', None) if request.user.is_authenticated else None
		errors = {}
		to_create = []
		all_cases = [parent] + children
		for c in all_cases:
			file = request.FILES.get(f'doc_{c.id}')
			desc = request.POST.get(f'desc_{c.id}') or f"Final document for {c.get_status_display()}"
			if not file:
				errors[c.id] = 'Document is required for this case.'
				continue
			# Basic validations
			if file.size > 5 * 1024 * 1024:
				errors[c.id] = 'File too large (max 5MB).'
				continue
			allowed = [
				'application/pdf',
				'image/jpeg','image/png','image/gif','image/webp',
				'application/msword',
				'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
			]
			if hasattr(file, 'content_type') and file.content_type not in allowed:
				errors[c.id] = 'Unsupported file type. Upload PDF, DOC/DOCX, or image.'
				continue
			to_create.append((c, file, desc))
		if errors:
			# Re-render with inline error messages
			return render(request, 'cases/case_upload_documents_group.html', {
				'parent': parent,
				'children': children,
				'errors': errors,
			})
		# Save docs replacing only prior finals; keep receipts
		for c, file, desc in to_create:
			prior_finals = list(c.documents.filter(is_receipt=False))
			if prior_finals:
				for d in prior_finals:
					try:
						if d.file:
							d.file.delete(save=False)
					except Exception:
						pass
					d.delete()
				CaseUpdate.objects.create(case=c, action='document_replaced', remark='Replaced after finalization (group upload).')
			else:
				CaseUpdate.objects.create(case=c, action='document_uploaded', remark='Uploaded after finalization (group upload).')
			CaseDocument.objects.create(case=c, file=file, uploaded_by=uploader, description=desc, is_receipt=False)
		messages.success(request, 'All documents uploaded successfully.')
		return redirect('post_finalize_options', case_id=parent.id)

	# GET request or initial render
	return render(request, 'cases/case_upload_documents_group.html', {
		'parent': parent,
		'children': children,
		'errors': {},
	})


# =========================
# FINAL DOC + STATUS (combined)
# =========================
class FinalizeWithDocumentForm(forms.Form):
	STATUS_CHOICES = (
		('positive', 'Positive'),
		('negative', 'Negative'),
	)
	supporting_document = forms.FileField(required=True, widget=forms.ClearableFileInput(attrs={'accept':'.pdf,.doc,.docx,image/*','class':'w-full border rounded p-2'}))
	document_description = forms.CharField(required=False, max_length=200)
	status = forms.ChoiceField(choices=STATUS_CHOICES, required=True)
	remark = forms.CharField(required=False, max_length=500)

	def clean(self):
		cd = super().clean()
		f = self.files.get('supporting_document')
		if not f:
			self.add_error('supporting_document', 'Final document is required.')
		else:
			if hasattr(f, 'size') and f.size > 5 * 1024 * 1024:
				self.add_error('supporting_document', 'File too large (max 5MB).')
			allowed = [
				'application/pdf',
				'image/jpeg','image/png','image/gif','image/webp',
				'application/msword',
				'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
			]
			if hasattr(f, 'content_type') and f.content_type not in allowed:
				self.add_error('supporting_document', 'Unsupported file type. Upload PDF, DOC/DOCX, or image.')
		return cd


@advocate_or_admin_required
def case_finalize_with_document(request, case_id):
	"""Upload final document and set final status in one step when document is pending after SRO upload."""
	case = get_object_or_404(Case, id=case_id)
	# Only allow assigned advocate (or admin) to perform
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to update this case.")
		return redirect('view_cases')
	# Only when awaiting final doc
	if case.status not in ['document_pending', 'sro_document_pending']:
		messages.info(request, 'Final document can be uploaded only when the case is document pending.')
		return redirect('case_detail', case_id=case.id)

	children = list(case.child_cases.all())
	if request.method == 'POST':
		form = FinalizeWithDocumentForm(request.POST, request.FILES)
		if form.is_valid():
			# Save/replace final document (keep receipts)
			file = form.files['supporting_document']
			desc = form.cleaned_data.get('document_description') or f"Final document for {case.case_number}"
			# Replace existing final docs
			prior_finals = list(case.documents.filter(is_receipt=False))
			for d in prior_finals:
				try:
					if d.file:
						d.file.delete(save=False)
				except Exception:
					pass
				d.delete()
			CaseDocument.objects.create(
				case=case,
				file=file,
				uploaded_by=getattr(request.user, 'employee', None) if request.user.is_authenticated else None,
				description=desc,
				is_receipt=False
			)
			# Set final status and housekeeping
			new_status = form.cleaned_data['status']
			case.status = new_status
			case.completed_at = timezone.now()
			if not case.legal_reference_number:
				try:
					case.generate_legal_reference_number()
				except Exception:
					pass
			case.save()
			# Handle children uploads and optional finalization
			finalized_children = 0
			pending_children = 0
			for child in children:
				cfile = request.FILES.get(f'child_doc_{child.id}')
				cdesc = request.POST.get(f'child_desc_{child.id}') or f"Final document for {child.case_number}"
				if cfile:
					# Replace prior final docs for child and attach new
					for d in list(child.documents.filter(is_receipt=False)):
						try:
							if d.file:
								d.file.delete(save=False)
						except Exception:
							pass
						d.delete()
					CaseDocument.objects.create(
						case=child,
						file=cfile,
						uploaded_by=getattr(request.user, 'employee', None) if request.user.is_authenticated else None,
						description=cdesc,
						is_receipt=False
					)
					# Finalize child with same status
					child.status = new_status
					child.completed_at = timezone.now()
					if not child.legal_reference_number:
						try:
							child.generate_legal_reference_number()
						except Exception:
							pass
					child.save()
					try:
						CaseUpdate.objects.create(case=child, action=new_status, remark='Finalized with document upload (child)')
					except Exception:
						pass
					finalized_children += 1
				else:
					# If child already has a final document, allow status sync; else leave pending
					has_final = child.documents.filter(is_receipt=False).exists()
					if has_final:
						if child.status != new_status:
							child.status = new_status
						if not child.completed_at:
							child.completed_at = timezone.now()
						if not child.legal_reference_number:
							try:
								child.generate_legal_reference_number()
							except Exception:
								pass
						child.save()
						try:
							CaseUpdate.objects.create(case=child, action=new_status, remark='Finalized (no new document)')
						except Exception:
							pass
						finalized_children += 1
					else:
						pending_children += 1
			# Record update
			try:
				CaseUpdate.objects.create(case=case, action=new_status, remark=form.cleaned_data.get('remark') or 'Finalized with document upload')
			except Exception:
				pass
			if children:
				if pending_children:
					messages.success(request, f'Final document uploaded and status updated. Children finalized: {finalized_children}. Remaining without document: {pending_children}.')
				else:
					messages.success(request, f'Final document uploaded and status updated for parent and {finalized_children} child(ren).')
			else:
				messages.success(request, 'Final document uploaded and status updated.')
			return redirect('case_detail', case_id=case.id)
	else:
		form = FinalizeWithDocumentForm()
	return render(request, 'cases/finalize_with_document.html', {'form': form, 'case': case, 'children': children})


@admin_required
def delete_case(request, case_id):
	case = get_object_or_404(Case, id=case_id)
	
	# If trying to delete a child case, redirect to parent
	if case.parent_case:
		messages.warning(request, f"Cannot delete child case directly. Child cases are managed through the parent case.")
		return redirect('case_detail', case_id=case.parent_case.id)
	
	if request.method == 'POST':
		number = case.case_number
		case.delete()
		messages.success(request, f'Case {number} deleted.')
		return redirect('view_cases')
	return render(request, 'cases/delete_case_confirm.html', {'case': case})


@advocate_or_admin_required
def post_finalize_options(request, case_id):
	"""After finalization and document upload, ask whether to add child cases one-by-one."""
	case = get_object_or_404(Case, id=case_id)
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to view this case.")
		return redirect('view_cases')
	# Ensure parent has LRN
	if not case.legal_reference_number:
		case.generate_legal_reference_number(); case.save()
	# Compute top-level parent in case user finalized a child
	root_case = case
	while getattr(root_case, 'parent_case_id', None):
		root_case = root_case.parent_case
	return render(request, 'cases/post_finalize_options.html', {'case': case, 'root_case': root_case})


from .forms import ChildCaseForm

@advocate_or_admin_required
def add_child_case(request, case_id):
	# Resolve to the top-level parent to avoid creating child-of-child
	current = get_object_or_404(Case, id=case_id)
	parent = current
	while getattr(parent, 'parent_case_id', None):
		parent = parent.parent_case
	# Allow adding child cases even if parent is finalized.
	# This enables adding additional properties to be forwarded to SRO with the same final status.
	if not check_case_access(request.user, parent):
		messages.error(request, "You don't have permission to add a child case.")
		return redirect('view_cases')
	if request.method == 'POST':
		form = ChildCaseForm(request.POST, parent_case=parent)
		if form.is_valid():
			addr = form.cleaned_data.get('property_address')
			state = form.cleaned_data.get('state') or parent.state
			district = form.cleaned_data.get('district') or parent.district
			tehsil = form.cleaned_data.get('tehsil') or parent.tehsil
			branch = form.cleaned_data.get('branch') or parent.branch
			new_case = Case(
				applicant_name=parent.applicant_name,
				case_number=f"{parent.case_number}-{parent.child_cases.count()+1}",
				bank=parent.bank,
				case_type=parent.case_type,
				documents_present=parent.documents_present,
				# Inherit status from parent as requested
				status=parent.status,
				property_address=addr,
				state=state,
				district=district,
				tehsil=tehsil,
				branch=branch,
				assigned_advocate=parent.assigned_advocate,
				parent_case=parent,
			)
			# Mirror SRO forwarding flag from parent (useful when adding after finalization)
			new_case.forwarded_to_sro = parent.forwarded_to_sro
			new_case.save()
			# If parent is already finalized, generate LRN now and prompt upload on the child
			final_statuses = ['positive', 'positive_subject_tosearch', 'negative']
			if parent.status in final_statuses:
				new_case.generate_legal_reference_number(); new_case.save()
			try:
				CaseUpdate.objects.create(case=parent, action='child_created', remark=f"Created child {new_case.case_number} -> {new_case.legal_reference_number or '-'}")
			except Exception:
				pass
			# If finalized, redirect to upload document for this child case
			if parent.status in final_statuses:
				messages.success(request, f'Child case {new_case.case_number} created with LRN {new_case.legal_reference_number}. Please upload the document.')
				return redirect('case_upload_document', case_id=new_case.id)
			else:
				# Not finalized yet, stay on add child page
				messages.success(request, f'Child case {new_case.case_number} created. You can add another linked property.')
				return redirect('add_child_case', case_id=parent.id)
	else:
		form = ChildCaseForm(parent_case=parent)
	return render(request, 'cases/add_child_case.html', {'form': form, 'parent': parent})


# =========================
# CASE TYPE MANAGEMENT
# =========================
@admin_required
def create_case_type(request):
	if request.method == 'POST':
		form = CaseTypeForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Case Type created.')
			# Redirect back to creation page for rapid entry
			return redirect('create_case_type')
	else:
		form = CaseTypeForm()
	return render(request, 'cases/create_case_type.html', {'form': form})


@admin_required
def view_case_types(request):
	return render(request, 'cases/view_case_types.html', {'case_types': CaseType.objects.all()})


@admin_required
def delete_case_type(request, pk):
	ct = get_object_or_404(CaseType, pk=pk)
	referenced = ct.cases.exists()
	error_message = None
	if request.method == 'POST':
		if referenced:
			error_message = "Cannot delete this case type because it is attached to one or more cases."
		else:
			ct.delete()
			messages.success(request, 'Case Type deleted.')
			return redirect('view_case_types')
	return render(request, 'cases/delete_case_type_confirm.html', {'case_type': ct, 'error_message': error_message})



@admin_required
def edit_bank(request, pk):
	messages.info(request, 'Bank editing moved. Use the new Bank module.')
	return redirect('Bank:bank_detail', bank_id=pk)


@admin_required
def delete_bank(request, pk):
	messages.info(request, 'Use the Bank module to manage banks.')
	return redirect('Bank:viewbanks')



@admin_required
def view_branches(request):
	messages.info(request, 'Branches moved to Bank module.')
	return redirect('Bank:viewbanks')

@admin_required
def view_branches_by_bank(request, pk):
	return redirect('Bank:manage_bank_branches', bank_id=pk)


@admin_required
def create_branch(request):
	bank_id = request.GET.get('bank') or request.POST.get('bank_id')
	if bank_id:
		return redirect('Bank:manage_bank_branches', bank_id=bank_id)
	return redirect('Bank:viewbanks')

@admin_required
def edit_branch(request, pk):
	messages.info(request, 'Editing moved to Bank module.')
	# We don't have bank_id here; best effort: go to banks list
	return redirect('Bank:viewbanks')


@admin_required
def delete_branch(request, pk):
	messages.info(request, 'Delete branches in Bank module.')
	return redirect('Bank:viewbanks')


@admin_required
def view_bank_detail(request, pk):
	return redirect('Bank:bank_detail', bank_id=pk)


@admin_required  
def view_employee_detail(request, pk):
    """View detailed information about a specific employee"""
    employee = get_object_or_404(Employee, pk=pk)
    return render(request, 'cases/view_employee_detail.html', {'employee': employee})


# =========================
# LOCATION MANAGEMENT (ADMIN)
# =========================
@admin_required
def locations_states_list(request):
	states = State.objects.order_by('name')
	return render(request, 'cases/locations/states_list.html', {'states': states})

@admin_required
def locations_state_create(request):
	if request.method == 'POST':
		form = StateForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'State added.')
			return redirect('locations_states_list')
	else:
		form = StateForm()
	return render(request, 'cases/locations/state_form.html', {'form': form, 'title': 'Add State'})

@admin_required
def locations_state_edit(request, pk):
	state = get_object_or_404(State, pk=pk)
	if request.method == 'POST':
		form = StateForm(request.POST, instance=state)
		if form.is_valid():
			form.save()
			messages.success(request, 'State updated.')
			return redirect('locations_states_list')
	else:
		form = StateForm(instance=state)
	return render(request, 'cases/locations/state_form.html', {'form': form, 'title': 'Edit State'})

@admin_required
def locations_state_delete(request, pk):
	state = get_object_or_404(State, pk=pk)
	if request.method == 'POST':
		state.delete()
		messages.success(request, 'State deleted.')
		return redirect('locations_states_list')
	return render(request, 'cases/locations/confirm_delete.html', {'object': state, 'type': 'State'})

@admin_required
def locations_districts_list(request):
	q = (request.GET.get('q') or '').strip()
	state = (request.GET.get('state') or '').strip()
	qs = District.objects.select_related('state').all()
	if state:
		qs = qs.filter(state__name__icontains=state)
	if q:
		qs = qs.filter(name__icontains=q)
	districts = qs.order_by('state__name','name')[:500]
	return render(request, 'cases/locations/districts_list.html', {'districts': districts, 'q': q, 'state_q': state})

@admin_required
def locations_district_create(request):
	if request.method == 'POST':
		form = DistrictForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'District added.')
			return redirect('locations_districts_list')
	else:
		form = DistrictForm()
	return render(request, 'cases/locations/district_form.html', {'form': form, 'title': 'Add District'})

@admin_required
def locations_district_edit(request, pk):
	district = get_object_or_404(District, pk=pk)
	if request.method == 'POST':
		form = DistrictForm(request.POST, instance=district)
		if form.is_valid():
			form.save()
			messages.success(request, 'District updated.')
			return redirect('locations_districts_list')
	else:
		form = DistrictForm(instance=district)
	return render(request, 'cases/locations/district_form.html', {'form': form, 'title': 'Edit District'})

@admin_required
def locations_district_delete(request, pk):
	district = get_object_or_404(District, pk=pk)
	if request.method == 'POST':
		district.delete()
		messages.success(request, 'District deleted.')
		return redirect('locations_districts_list')
	return render(request, 'cases/locations/confirm_delete.html', {'object': district, 'type': 'District'})

@admin_required
def locations_tehsils_list(request):
	q = (request.GET.get('q') or '').strip()
	state = (request.GET.get('state') or '').strip()
	district = (request.GET.get('district') or '').strip()
	qs = Tehsil.objects.select_related('district','district__state').all()
	if state:
		qs = qs.filter(district__state__name__icontains=state)
	if district:
		qs = qs.filter(district__name__icontains=district)
	if q:
		qs = qs.filter(name__icontains=q)
	tehsils = qs.order_by('district__state__name','district__name','name')[:500]
	return render(request, 'cases/locations/tehsils_list.html', {'tehsils': tehsils, 'q': q, 'state_q': state, 'district_q': district})

@admin_required
def locations_tehsil_create(request):
	if request.method == 'POST':
		form = TehsilForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Tehsil added.')
			return redirect('locations_tehsils_list')
	else:
		form = TehsilForm()
	return render(request, 'cases/locations/tehsil_form.html', {'form': form, 'title': 'Add Tehsil'})

@admin_required
def locations_tehsil_edit(request, pk):
	tehsil = get_object_or_404(Tehsil, pk=pk)
	if request.method == 'POST':
		form = TehsilForm(request.POST, instance=tehsil)
		if form.is_valid():
			form.save()
			messages.success(request, 'Tehsil updated.')
			return redirect('locations_tehsils_list')
	else:
		form = TehsilForm(instance=tehsil)
	return render(request, 'cases/locations/tehsil_form.html', {'form': form, 'title': 'Edit Tehsil'})

@admin_required
def locations_tehsil_delete(request, pk):
	tehsil = get_object_or_404(Tehsil, pk=pk)
	if request.method == 'POST':
		tehsil.delete()
		messages.success(request, 'Tehsil deleted.')
		return redirect('locations_tehsils_list')
	return render(request, 'cases/locations/confirm_delete.html', {'object': tehsil, 'type': 'Tehsil'})


# =========================
# SRO DASHBOARD & UPDATE
# =========================
@sro_or_admin_required
def sro_dashboard(request):
	"""List cases forwarded to SRO that are either Positive Subject to Search or Negative."""
	search = request.GET.get('search', '').strip()
	qs = Case.objects.filter(
		parent_case__isnull=True,
		forwarded_to_sro=True,
		status__in=['positive_subject_tosearch', 'negative', 'positive']
	).select_related('bank','case_type','assigned_advocate').order_by('-updated_at')
	# Apply SRO scoping
	user_emp = getattr(request.user, 'employee', None)
	if user_emp and user_emp.employee_type == Employee.SRO and not user_emp.is_super_sro:
		state_names = list(user_emp.allowed_states.values_list('name', flat=True))
		district_names = list(user_emp.allowed_districts.values_list('name', flat=True))
		tehsil_names = list(user_emp.allowed_tehsils.values_list('name', flat=True))
		conds = Q()
		if state_names:
			conds |= Q(state__in=state_names)
		if district_names:
			conds |= Q(district__in=district_names)
		if tehsil_names:
			conds |= Q(tehsil__in=tehsil_names)
		if conds:
			qs = qs.filter(conds)
		else:
			qs = qs.none()
	if search:
		qs = qs.filter(
			Q(applicant_name__icontains=search) |
			Q(case_number__icontains=search) |
			Q(legal_reference_number__icontains=search) |
			Q(child_cases__applicant_name__icontains=search) |
			Q(child_cases__case_number__icontains=search) |
			Q(child_cases__legal_reference_number__icontains=search)
		).distinct()
	return render(request, 'cases/sro_dashboard.html', {
		'cases': qs,
		'search_query': search,
	})


@sro_or_admin_required
def sro_update_case(request, case_id):
	"""Allow SRO to upload receipt and mark case Positive (if appropriate)."""
	case = get_object_or_404(Case, id=case_id)
	# Enforce SRO scoping for non-super SROs
	user_emp = getattr(request.user, 'employee', None)
	if user_emp and user_emp.employee_type == Employee.SRO and not user_emp.is_super_sro:
		allowed = (
			user_emp.allowed_states.filter(name__iexact=case.state).exists() or
			user_emp.allowed_districts.filter(name__iexact=case.district).exists() or
			user_emp.allowed_tehsils.filter(name__iexact=case.tehsil).exists()
		)
		if not allowed:
			messages.error(request, 'You do not have rights to update this case.')
			return redirect('dashboard')
	if not case.forwarded_to_sro or case.status not in ['positive_subject_tosearch', 'negative', 'positive']:
		messages.error(request, 'This case is not eligible for SRO update.')
		return redirect('dashboard')

	if request.method == 'POST':
		form = SROUpdateForm(request.POST, request.FILES)
		if form.is_valid():
			# Save receipt as the ONLY CaseDocument for this case
			receipt_file = form.files['supporting_document']
			description = form.cleaned_data.get('document_description') or 'SRO receipt'
			uploader = getattr(request.user, 'employee', None) if request.user.is_authenticated else None

			# Replace only previous receipts; preserve any final document(s)
			for d in list(case.documents.filter(is_receipt=True)):
				try:
					if d.file:
						d.file.delete(save=False)
				except Exception:
					pass
				d.delete()
			CaseUpdate.objects.create(case=case, action='document_uploaded', remark='SRO uploaded receipt document.')

			CaseDocument.objects.create(
				case=case,
				file=receipt_file,
				uploaded_by=uploader,
				description=description,
				is_receipt=True
			)
			# Update case fields: capture receipt, but send back to advocate for final doc upload
			case.receipt_number = form.cleaned_data.get('receipt_number') or case.receipt_number
			case.receipt_amount = form.cleaned_data.get('receipt_amount')
			case.receipt_expense = form.cleaned_data.get('receipt_expense')
			# New flow: not finalizing; request document upload by advocate (SRO-specific pending)
			case.status = 'sro_document_pending'
			case.forwarded_to_sro = False
			case.completed_at = None
			case.save()
			# Ensure child cases mirror parent status
			try:
				case.propagate_status_to_children()
			except Exception:
				pass
			CaseUpdate.objects.create(case=case, action='sro_update', remark=f"SRO uploaded receipt; sent back to advocate. Amount={case.receipt_amount} | ReceiptNo={case.receipt_number or '-'}")
			messages.success(request, 'Receipt uploaded. Case returned to Advocate for document upload.')
			return redirect('dashboard')
	else:
		form = SROUpdateForm(initial={'receipt_number': case.receipt_number, 'receipt_expense': case.receipt_expense, 'receipt_amount': case.receipt_amount})

	return render(request, 'cases/sro_update_case.html', {'form': form, 'case': case})


@sro_or_admin_required
def sro_update_group(request, case_id):
	"""SRO uploads receipts for a parent case and all its child cases in one go.
	After upload, set status=sro_document_pending and forwarded_to_sro=False for parent + children.
	"""
	parent = get_object_or_404(Case, id=case_id)
	# Enforce SRO scoping for non-super SROs
	user_emp = getattr(request.user, 'employee', None)
	if user_emp and user_emp.employee_type == Employee.SRO and not user_emp.is_super_sro:
		allowed = (
			user_emp.allowed_states.filter(name__iexact=parent.state).exists() or
			user_emp.allowed_districts.filter(name__iexact=parent.district).exists() or
			user_emp.allowed_tehsils.filter(name__iexact=parent.tehsil).exists()
		)
		if not allowed:
			messages.error(request, 'You do not have rights to update this case.')
			return redirect('dashboard')
	if not parent.forwarded_to_sro or parent.status not in ['positive_subject_tosearch', 'negative', 'positive']:
		messages.error(request, 'This case is not eligible for SRO update.')
		return redirect('dashboard')

	children = list(parent.child_cases.all())
	cases = [parent] + children

	if request.method == 'POST':
		uploader = getattr(request.user, 'employee', None) if request.user.is_authenticated else None
		errors = {}
		created_docs = 0
		for c in cases:
			f = request.FILES.get(f'doc_{c.id}')
			amt = request.POST.get(f'amt_{c.id}')
			exp = request.POST.get(f'exp_{c.id}')
			rec = request.POST.get(f'rec_{c.id}')
			if not f:
				errors[c.id] = 'Receipt document is required.'
				continue
			# basic validations
			if hasattr(f, 'size') and f.size > 5 * 1024 * 1024:
				errors[c.id] = 'File too large (max 5MB).'
				continue
			allowed = [
				'application/pdf',
				'image/jpeg','image/png','image/gif','image/webp',
				'application/msword',
				'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
			]
			if hasattr(f, 'content_type') and f.content_type not in allowed:
				errors[c.id] = 'Unsupported file type. Upload PDF, DOC/DOCX, or image.'
				continue
			# Replace only previous receipts; preserve any final document(s)
			for d in list(c.documents.filter(is_receipt=True)):
				try:
					if d.file:
						d.file.delete(save=False)
				except Exception:
					pass
				d.delete()
			CaseDocument.objects.create(case=c, file=f, uploaded_by=uploader, description='SRO receipt', is_receipt=True)
			# Update receipt metadata and status
			try:
				c.receipt_amount = amt or c.receipt_amount
				c.receipt_expense = exp or c.receipt_expense
				c.receipt_number = rec or c.receipt_number
			except Exception:
				pass
			c.status = 'sro_document_pending'
			c.forwarded_to_sro = False
			c.completed_at = None
			c.save()
			try:
				CaseUpdate.objects.create(case=c, action='sro_update', remark='SRO uploaded receipt (group). Returned to advocate for document upload.')
			except Exception:
				pass
			created_docs += 1
		if errors:
			# Attach per-case error message to objects for easy template access
			for c in cases:
				msg = errors.get(c.id)
				if msg:
					setattr(c, 'form_error', msg)
			# Also ensure parent has attribute if present in errors
			pmsg = errors.get(parent.id)
			if pmsg:
				setattr(parent, 'form_error', pmsg)
			return render(request, 'cases/sro_group_update.html', {
				'parent': parent,
				'children': children,
				'errors': errors,
			})
		messages.success(request, f'Receipts uploaded for {created_docs} case(s). Returned to advocate for document upload.')
		return redirect('dashboard')

	return render(request, 'cases/sro_group_update.html', {
		'parent': parent,
		'children': children,
		'errors': {},
	})


# =========================
# SRO RIGHTS MANAGEMENT (ADMIN)
# =========================
@admin_required
def sro_manage(request):
	"""Admin list of SRO employees with quick search and links to edit scope."""
	q = (request.GET.get('q') or '').strip()
	sros = Employee.objects.filter(employee_type=Employee.SRO).order_by('name')
	if q:
		sros = sros.filter(Q(name__icontains=q) | Q(employee_id__icontains=q) | Q(user__username__icontains=q))
	return render(request, 'cases/sro/sro_list.html', {'sros': sros, 'q': q})


@admin_required
def sro_manage_edit(request, pk):
	"""Edit SRO scoping (super/non-super, allowed states/districts/tehsils)."""
	sro = get_object_or_404(Employee, pk=pk, employee_type=Employee.SRO)
	if request.method == 'POST':
		form = SROScopeForm(request.POST, instance=sro)
		if form.is_valid():
			form.save()
			messages.success(request, 'SRO scope updated successfully.')
			return redirect('sro_manage')
	else:
		form = SROScopeForm(instance=sro)
	return render(request, 'cases/sro/sro_scope_form.html', {'form': form, 'sro': sro})