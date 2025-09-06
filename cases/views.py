"""Case management view functions.

This file was re-written in UTF-8 (previously saved as UTF-16 which introduced
embedded NUL bytes and caused: SyntaxError: source code string cannot contain null bytes.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required  # retained if needed elsewhere
from django.contrib.auth.models import User  # retained for potential future use
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count

from .models import (
	CaseType, Branch, BranchCaseType, Bank,
	Employee, Case, CaseUpdate
)
from .forms import (
	CaseTypeForm, BranchForm, BranchCaseTypeForm, BankForm, EmployeeForm, EmployeeEditForm,
	CaseCreationForm, CaseAssignmentForm, CaseWorkForm, AdditionalCaseAddressForm, CaseActionForm
)
from .decorators import (
	admin_required, advocate_or_admin_required,
	get_user_employee, check_case_access
)

# =========================
# CASE MANAGEMENT
# =========================
@admin_required
def create_case(request):
	if request.method == 'POST':
		form = CaseCreationForm(request.POST)
		if form.is_valid():
			case = form.save(commit=False)
			if not case.case_number:
				timestamp = timezone.now().strftime('%y%m%d%H%M%S')
				bank_code = case.bank.name[:3].upper()
				case.case_number = f"{bank_code}-{timestamp}"
			case.status = 'pending' if case.assigned_advocate else 'pending_assignment'
			case.save()
			if case.assigned_advocate:
				messages.success(request, f"Case {case.case_number} created and assigned to {case.assigned_advocate.name}.")
			else:
				messages.success(request, f"Case {case.case_number} created and queued for assignment.")
			return redirect('view_cases')
	else:
		form = CaseCreationForm()
	return render(request, 'cases/create_case.html', {'form': form})


@advocate_or_admin_required
def view_cases(request):
	employee = get_user_employee(request.user)
	is_admin = request.user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or request.user.is_superuser

	if is_admin:
		cases = Case.objects.select_related('bank', 'case_type', 'assigned_advocate').all().order_by('-created_at')
	elif employee and employee.employee_type == 'advocate':
		cases = Case.objects.filter(assigned_advocate=employee).select_related('bank', 'case_type', 'assigned_advocate').order_by('-created_at')
	else:
		cases = Case.objects.none()

	pending_assignment_buckets = [('Pending Assignment', 'pending_assignment', 'orange')]
	pending_buckets = [('Pending', 'pending', 'purple')]
	active_buckets = [
		('On Hold', 'on_hold', 'blue'),
		('On Query', 'on_query', 'yellow'),
		('Document Pending', 'document_pending', 'indigo'),
	]
	completed_positive_buckets = [('Positive', 'positive', 'emerald')]
	completed_negative_buckets = [('Negative', 'negative', 'red')]

	all_buckets = pending_assignment_buckets + pending_buckets + active_buckets + completed_positive_buckets + completed_negative_buckets
	status_counts = {s: 0 for s in [b[1] for b in all_buckets]}
	for c in cases:
		if c.status in status_counts:
			status_counts[c.status] += 1

	return render(request, 'cases/view_cases.html', {
		'cases': cases,
		'pending_assignment_buckets': pending_assignment_buckets,
		'pending_buckets': pending_buckets,
		'active_buckets': active_buckets,
		'completed_positive_buckets': completed_positive_buckets,
		'completed_negative_buckets': completed_negative_buckets,
		'status_counts': status_counts,
		'is_admin': is_admin,
	})


@advocate_or_admin_required
def advocate_cases_filtered(request, filter_type):
	employee = get_user_employee(request.user)
	is_admin = request.user.groups.filter(name__in=['ADMIN','CO-ADMIN']).exists() or request.user.is_superuser
	qs = Case.objects.all()
	title = 'All Cases'
	if employee and employee.employee_type == 'advocate' and not is_admin:
		qs = qs.filter(assigned_advocate=employee)
	status_map = {
		'active': ['on_hold','on_query','document_pending'],
		'pending': ['pending'],
		'pending_assignment': ['pending_assignment'],
		'document_pending': ['document_pending'],
		'query': ['on_query'],
		'hold': ['on_hold'],
		'doc_hold': ['document_pending'],
		'completed': ['positive','negative'],
		'hold_query_doc': ['on_hold','on_query','document_pending'],
		'all': ['pending_assignment','pending','document_pending','on_hold','on_query','positive','negative']
	}
	if filter_type in status_map:
		qs = qs.filter(status__in=status_map[filter_type])
		title = filter_type.replace('_',' ').title() + ' Cases'
	cases = qs.select_related('bank','case_type','assigned_advocate').order_by('-updated_at')

	pending_assignment_buckets = [('Pending Assignment', 'pending_assignment', 'orange')]
	pending_buckets = [('Pending', 'pending', 'purple')]
	active_buckets = [
		('On Hold', 'on_hold', 'blue'),
		('On Query', 'on_query', 'yellow'),
		('Document Pending', 'document_pending', 'indigo'),
	]
	completed_positive_buckets = [('Positive', 'positive', 'emerald')]
	completed_negative_buckets = [('Negative', 'negative', 'red')]

	all_buckets = pending_assignment_buckets + pending_buckets + active_buckets + completed_positive_buckets + completed_negative_buckets
	status_counts = {s: 0 for s in [b[1] for b in all_buckets]}
	for c in cases:
		if c.status in status_counts:
			status_counts[c.status] += 1

	return render(request, 'cases/view_cases.html', {
		'cases': cases,
		'list_title': title,
		'pending_assignment_buckets': pending_assignment_buckets,
		'pending_buckets': pending_buckets,
		'active_buckets': active_buckets,
		'completed_positive_buckets': completed_positive_buckets,
		'completed_negative_buckets': completed_negative_buckets,
		'status_counts': status_counts,
		'is_admin': is_admin,
	})


@admin_required
def view_pending_cases(request):
	pending_cases = Case.objects.filter(status__in=['pending_assignment', 'document_pending']).select_related('bank','case_type','assigned_advocate').order_by('-created_at')
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
			messages.success(request, f"Case {case.case_number} assigned to {case.assigned_advocate.name}.")
			return redirect('view_pending_cases')
	else:
		form = CaseAssignmentForm(instance=case)
	return render(request, 'cases/assign_case_advocate.html', {'form': form, 'case': case})


@advocate_or_admin_required
def case_detail(request, case_id):
	case = get_object_or_404(Case, id=case_id)
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to view this case.")
		return redirect('view_cases')
	return render(request, 'cases/case_detail.html', {'case': case})


@advocate_or_admin_required
def work_on_case(request, case_id):
	case = get_object_or_404(Case, id=case_id)
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to edit this case.")
		return redirect('view_cases')

	extra_address_forms = []
	form_count = int(request.POST.get('form_count', 0)) if request.method == 'POST' else 0

	if request.method == 'POST':
		form = CaseWorkForm(request.POST, instance=case)
		valid_forms = form.is_valid()
		all_addresses = []
		for i in range(form_count):
			addr_data = {
				'property_address': request.POST.get(f'property_address_{i}', ''),
				'state': request.POST.get(f'state_{i}', ''),
				'district': request.POST.get(f'district_{i}', ''),
				'tehsil': request.POST.get(f'tehsil_{i}', ''),
				'branch': request.POST.get(f'branch_{i}', ''),
				'reference_name': request.POST.get(f'reference_name_{i}', ''),
				'case_name': request.POST.get(f'case_name_{i}', ''),
			}
			extra_form = AdditionalCaseAddressForm(addr_data)
			extra_address_forms.append(extra_form)
			if extra_form.is_valid():
				all_addresses.append(extra_form.cleaned_data)
			else:
				valid_forms = False

		if valid_forms:
			case = form.save()
			parent = case
			for addr in all_addresses:
				if not addr['property_address']:
					continue
				Case.objects.create(
					applicant_name=parent.applicant_name,
					case_number=f"{parent.case_number}-{parent.child_cases.count()+1}",
					bank=parent.bank,
					case_type=parent.case_type,
					documents_present=parent.documents_present,
					assigned_advocate=parent.assigned_advocate,
					status=parent.status,
					property_address=addr['property_address'],
					state=addr['state'],
					district=addr['district'],
					tehsil=addr['tehsil'],
					branch=addr['branch'],
					reference_name=addr['reference_name'],
					case_name=addr['case_name'],
					employee=parent.employee,
					parent_case=parent
				)
			messages.success(request, 'Case details saved and additional cases created (if any).')
			return redirect('case_detail', case_id=case.id)
	else:
		form = CaseWorkForm(instance=case)
		extra_address_forms = [AdditionalCaseAddressForm()]

	return render(request, 'cases/work_on_case.html', {
		'form': form,
		'extra_forms': extra_address_forms,
		'case': case
	})


@advocate_or_admin_required
def case_action(request, case_id):
	case = get_object_or_404(Case, id=case_id)
	if not check_case_access(request.user, case):
		messages.error(request, "You don't have permission to act on this case.")
		return redirect('view_cases')

	if request.method == 'POST':
		form = CaseActionForm(request.POST)
		if form.is_valid():
			action = form.cleaned_data['action']
			remark = form.cleaned_data.get('remark')
			forward = form.cleaned_data.get('forward_to_sro', False)
			status_map = {
				'query': 'on_query',
				'hold': 'on_hold',
				'document_hold': 'document_pending',
				'positive': 'positive',
				'negative': 'negative'
			}
			if action not in status_map:
				messages.error(request, 'Invalid action.')
				return redirect('case_action', case_id=case.id)
			if action in ['positive','negative'] and not case.has_complete_details():
				messages.error(request, 'Complete all required case details before finalizing.')
				return redirect('work_on_case', case_id=case.id)
			case.status = status_map[action]
			if action in ['positive','negative']:
				case.generate_legal_reference_number()
				case.completed_at = timezone.now()
			if action == 'negative' and forward:
				case.forwarded_to_sro = True
			case.save()
			CaseUpdate.objects.create(case=case, action=action, remark=remark)
			messages.success(request, f'Case updated to {case.get_status_display()}')
			return redirect('case_detail', case_id=case.id)
	else:
		form = CaseActionForm()
	return render(request, 'cases/case_action.html', {'form': form, 'case': case})


@admin_required
def delete_case(request, case_id):
	case = get_object_or_404(Case, id=case_id)
	if request.method == 'POST':
		number = case.case_number
		case.delete()
		messages.success(request, f'Case {number} deleted.')
		return redirect('view_cases')
	return render(request, 'cases/delete_case_confirm.html', {'case': case})


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
			return redirect('view_case_types')
	else:
		form = CaseTypeForm()
	return render(request, 'cases/create_case_type.html', {'form': form})


@admin_required
def view_case_types(request):
	return render(request, 'cases/view_case_types.html', {'case_types': CaseType.objects.all()})


@admin_required
def delete_case_type(request, pk):
	ct = get_object_or_404(CaseType, pk=pk)
	if request.method == 'POST':
		ct.delete()
		messages.success(request, 'Case Type deleted.')
		return redirect('view_case_types')
	return render(request, 'cases/delete_case_type_confirm.html', {'case_type': ct})


# =========================
# BANK MANAGEMENT
# =========================
@admin_required
def create_bank(request):
	if request.method == 'POST':
		form = BankForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Bank created.')
			return redirect('view_banks')
	else:
		form = BankForm()
	return render(request, 'cases/create_bank.html', {'form': form})


@admin_required
def view_banks(request):
	banks = Bank.objects.annotate(branch_count=Count('branches'))
	return render(request, 'cases/view_banks.html', {'banks': banks})


@admin_required
def edit_bank(request, pk):
	bank = get_object_or_404(Bank, pk=pk)
	if request.method == 'POST':
		form = BankForm(request.POST, instance=bank)
		if form.is_valid():
			form.save()
			messages.success(request, 'Bank updated.')
			return redirect('view_banks')
	else:
		form = BankForm(instance=bank)
	return render(request, 'cases/create_bank.html', {'form': form, 'edit_mode': True})


@admin_required
def delete_bank(request, pk):
	bank = get_object_or_404(Bank, pk=pk)
	if request.method == 'POST':
		bank.delete()
		messages.success(request, 'Bank deleted.')
		return redirect('view_banks')
	return render(request, 'cases/delete_bank_confirm.html', {'bank': bank})


# =========================
# BRANCH MANAGEMENT
# =========================
@admin_required
def create_branch(request):
	if request.method == 'POST':
		form = BranchForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Branch created.')
			return redirect('view_branches')
	else:
		form = BranchForm()
	return render(request, 'cases/create_branch.html', {'form': form})


@admin_required
def view_branches(request):
	branches = Branch.objects.select_related('bank')
	return render(request, 'cases/view_branches.html', {'branches': branches})


@admin_required
def view_branches_by_bank(request, pk):
	bank = get_object_or_404(Bank, pk=pk)
	branches = Branch.objects.filter(bank=bank)
	return render(request, 'cases/view_branches.html', {'branches': branches, 'bank': bank})


@admin_required
def edit_branch(request, pk):
	branch = get_object_or_404(Branch, pk=pk)
	if request.method == 'POST':
		form = BranchForm(request.POST, instance=branch)
		if form.is_valid():
			form.save()
			messages.success(request, 'Branch updated.')
			return redirect('view_branches')
	else:
		form = BranchForm(instance=branch)
	return render(request, 'cases/create_branch.html', {'form': form, 'edit_mode': True})


@admin_required
def delete_branch(request, pk):
	branch = get_object_or_404(Branch, pk=pk)
	if request.method == 'POST':
		branch.delete()
		messages.success(request, 'Branch deleted.')
		return redirect('view_branches')
	return render(request, 'cases/delete_branch_confirm.html', {'branch': branch})


# =========================
# BRANCH CASE TYPE MANAGEMENT
# =========================
@admin_required
def assign_case_type(request, pk):
	branch = get_object_or_404(Branch, pk=pk)
	if request.method == 'POST':
		form = BranchCaseTypeForm(request.POST)
		if form.is_valid():
			instance = form.save(commit=False)
			instance.branch = branch
			instance.save()
			messages.success(request, 'Case Type assigned to branch.')
			return redirect('view_branches')
	else:
		form = BranchCaseTypeForm()
	return render(request, 'cases/assign_case_type.html', {'form': form, 'branch': branch})


@admin_required
def edit_branch_case_type(request, pk):
	bct = get_object_or_404(BranchCaseType, pk=pk)
	if request.method == 'POST':
		form = BranchCaseTypeForm(request.POST, instance=bct)
		if form.is_valid():
			form.save()
			messages.success(request, 'Branch-Case Type updated.')
			return redirect('view_branches')
	else:
		form = BranchCaseTypeForm(instance=bct)
	return render(request, 'cases/assign_case_type.html', {'form': form, 'branch': bct.branch, 'edit_mode': True})


@admin_required
def delete_branch_case_type(request, pk):
	bct = get_object_or_404(BranchCaseType, pk=pk)
	if request.method == 'POST':
		bct.delete()
		messages.success(request, 'Branch-Case Type deleted.')
		return redirect('view_branches')
	return render(request, 'cases/delete_branch_case_type_confirm.html', {'branch_case_type': bct})

