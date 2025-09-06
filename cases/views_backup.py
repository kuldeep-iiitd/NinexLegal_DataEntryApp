from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .models import CaseType, Branch, BranchCaseType, Bank, Employee, Case, CaseUpdate
from django.utils import timezone
from django.db.models import Count
from .forms import (
    CaseTypeForm, BranchForm, BranchCaseTypeForm, BankForm, EmployeeForm, EmployeeEditForm,
    CaseCreationForm, CaseAssignmentForm, CaseWorkForm, AdditionalCaseAddressForm, CaseActionForm
)
from .decorators import admin_required, advocate_or_admin_required, get_user_employee, check_case_access

# Case Management Views
@admin_required
def create_case(request):
    if request.method == 'POST':
        form = CaseCreationForm(request.POST)
        if form.is_valid():
            case = form.save(commit=False)
            # Generate unique case number with timestamp and bank identifier
            timestamp = timezone.now().strftime("%y%m%d%H%M")
            bank_code = case.bank.name[:3].upper()
            case.case_number = f"{bank_code}-{timestamp}"
            case.status = 'pending'  # Change default status to pending
            case.save()
            messages.success(request, f'Case {case.case_number} created successfully.')
            return redirect('view_cases')
    else:
        form = CaseCreationForm()
    return render(request, 'cases/create_case.html', {'form': form})


def view_cases(request):
    employee = get_user_employee(request.user)
    is_admin = request.user.groups.filter(name__in=['ADMIN','CO-ADMIN']).exists() or request.user.is_superuser
    
    # If user is an advocate and NOT admin, show only cases assigned to them
    if employee and employee.employee_type == 'advocate' and not is_admin:
        cases = Case.objects.filter(assigned_advocate=employee).select_related('bank', 'case_type', 'assigned_advocate')
    else:
        cases = Case.objects.all().select_related('bank', 'case_type', 'assigned_advocate')
    
    # Group 1: Pending Assignment Section
    pending_assignment_buckets = [
        ('Pending Assignment', 'pending_assignment', 'orange'),
    ]
    
    # Group 2: Pending Section
    pending_buckets = [
        ('Pending', 'pending', 'purple'),
    ]
    
    # Group 3: Hold, Query, Document Pending Section
    active_buckets = [
        ('On Hold', 'on_hold', 'blue'),
        ('On Query', 'on_query', 'yellow'),
        ('Document Pending', 'document_pending', 'indigo'),
    ]
    
    # Group 4: Completed Sections
    completed_buckets = [
        ('Positive', 'positive', 'green'),
        ('Negative', 'negative', 'red'),
    ]

    return render(request, 'cases/view_cases.html', {
        'cases': cases,
        'pending_assignment_buckets': pending_assignment_buckets,
        'pending_buckets': pending_buckets,
        'active_buckets': active_buckets,
        'completed_buckets': completed_buckets,
    })


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
        'hold_query_doc': ['on_hold','on_query','document_pending']
    }
    if filter_type in status_map:
        qs = qs.filter(status__in=status_map[filter_type])
        title = filter_type.replace('_',' ').title() + ' Cases'
    cases = qs.select_related('bank','case_type','assigned_advocate').order_by('-updated_at')

    # Reuse same bucket data so template works identically
    # Group 1: Pending Assignment Section
    pending_assignment_buckets = [
        ('Pending Assignment', 'pending_assignment', 'orange'),
    ]
    
    # Group 2: Pending Section
    pending_buckets = [
        ('Pending', 'pending', 'purple'),
    ]
    
    # Group 3: Hold, Query, Document Pending Section
    active_buckets = [
        ('On Hold', 'on_hold', 'blue'),
        ('On Query', 'on_query', 'yellow'),
        ('Document Pending', 'document_pending', 'indigo'),
    ]
    
    # Group 4: Completed Sections
    completed_buckets = [
        ('Positive', 'positive', 'green'),
        ('Negative', 'negative', 'red'),
    ]

    return render(request, 'cases/view_filtered_cases.html', {
        'cases': cases,
        'title': title,
        'filter_type': filter_type,
        'pending_assignment_buckets': pending_assignment_buckets,
        'pending_buckets': pending_buckets,
        'active_buckets': active_buckets,
        'completed_buckets': completed_buckets,
    })


def view_pending_cases(request):
    cases = Case.objects.filter(status='pending_assignment')
    return render(request, 'cases/view_pending_cases.html', {'cases': cases})


@admin_required
def assign_case_advocate(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    if request.method == 'POST':
        form = CaseAssignmentForm(request.POST, instance=case)
        if form.is_valid():
            updated_case = form.save(commit=False)
            updated_case.status = 'pending'  # Change from 'on_hold' to 'pending'
            updated_case.save()
            messages.success(request, f'Case assigned to {updated_case.assigned_advocate.name} successfully.')
            return redirect('view_cases')
    else:
        form = CaseAssignmentForm(instance=case)
    return render(request, 'cases/assign_case_advocate.html', {'form': form, 'case': case})


@check_case_access
def case_detail(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    # More features can be added here such as case history
    return render(request, 'cases/case_detail.html', {'case': case})


@check_case_access
def work_on_case(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    extra_address_forms = []
    
    if request.method == 'POST':
        form = CaseWorkForm(request.POST, instance=case)
        # Handle multiple address forms - determine how many were submitted
        form_count = int(request.POST.get('form_count', 0))
        extra_address_forms = []

        # Process main form
        valid_forms = form.is_valid()
        
        # Process additional address forms
        all_addresses = []
        for i in range(form_count):
            address_form_data = {
                'property_address': request.POST.get(f'property_address_{i}', ''),
                'state': request.POST.get(f'state_{i}', ''),
                'district': request.POST.get(f'district_{i}', ''),
                'tehsil': request.POST.get(f'tehsil_{i}', ''),
                'branch': request.POST.get(f'branch_{i}', ''),
                'reference_name': request.POST.get(f'reference_name_{i}', ''),
                'case_name': request.POST.get(f'case_name_{i}', ''),
            }
            
            # Create a form instance with the data
            extra_form = AdditionalCaseAddressForm(address_form_data)
            extra_address_forms.append(extra_form)
            
            if extra_form.is_valid():
                all_addresses.append(extra_form.cleaned_data)
            else:
                valid_forms = False
        
        if valid_forms:
            # Update main case
            case = form.save()
            
            # Create additional cases for each valid address
            parent = case
            for address_data in all_addresses:
                # Skip empty forms
                if not address_data['property_address']:
                    continue
                    
                # Create child case for each additional property address
                Case.objects.create(
                    applicant_name=parent.applicant_name,
                    case_number=f"{parent.case_number}-{Case.objects.filter(parent_case=parent).count() + 1}",
                    bank=parent.bank,
                    case_type=parent.case_type,
                    documents_present=parent.documents_present,
                    assigned_advocate=parent.assigned_advocate,
                    status=parent.status,
                    property_address=address_data['property_address'],
                    state=address_data['state'],
                    district=address_data['district'],
                    tehsil=address_data['tehsil'],
                    branch=address_data['branch'],
                    reference_name=address_data['reference_name'],
                    case_name=address_data['case_name'],
                    employee=parent.employee,
                    parent_case=parent
                )
            messages.success(request, 'Case details saved and additional cases created (if any).')
            return redirect('case_detail', case_id=case.id)
    else:
        form = CaseWorkForm(instance=case)
        extra_address_forms = [AdditionalCaseAddressForm()]  # start with one blank

    return render(request, 'cases/work_on_case.html', {
        'form': form,
        'extra_forms': extra_address_forms,
        'case': case
    })


@check_case_access
def case_action(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    
    if request.method == 'POST':
        form = CaseActionForm(request.POST)
        if form.is_valid():
            # Update case status based on action
            action = form.cleaned_data['action']
            remark = form.cleaned_data['remark']
            
            # Update case status
            case.status = action
            
            # Generate legal reference number for positive/negative cases
            if action in ['positive', 'negative'] and not case.legal_reference_number:
                case.legal_reference_number = case.generate_legal_reference_number()
                case.completed_at = timezone.now()
                
            case.save()
            
            # Create case update record
            CaseUpdate.objects.create(
                case=case,
                action=action,
                remark=remark
            )
            
            messages.success(request, f'Case status updated to {case.get_status_display()}.')
            return redirect('view_cases')
    else:
        form = CaseActionForm()
        
    return render(request, 'cases/case_action.html', {
        'form': form,
        'case': case
    })


@admin_required
def delete_case(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    if request.method == 'POST':
        case.delete()
        messages.success(request, 'Case deleted successfully.')
        return redirect('view_cases')
    return render(request, 'cases/delete_case_confirm.html', {'case': case})


# Case Type Views
@admin_required
def create_case_type(request):
    if request.method == 'POST':
        form = CaseTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Case Type created successfully.')
            return redirect('view_case_types')
    else:
        form = CaseTypeForm()
    return render(request, 'cases/create_case_type.html', {'form': form})


@admin_required
def view_case_types(request):
    case_types = CaseType.objects.all()
    return render(request, 'cases/view_case_types.html', {'case_types': case_types})


@admin_required
def delete_case_type(request, pk):
    case_type = get_object_or_404(CaseType, pk=pk)
    if request.method == 'POST':
        case_type.delete()
        messages.success(request, 'Case Type deleted successfully.')
        return redirect('view_case_types')
    return render(request, 'cases/delete_case_type_confirm.html', {'case_type': case_type})


# Bank Views
@admin_required
def create_bank(request):
    if request.method == 'POST':
        form = BankForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bank created successfully.')
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
            messages.success(request, 'Bank updated successfully.')
            return redirect('view_banks')
    else:
        form = BankForm(instance=bank)
    return render(request, 'cases/create_bank.html', {'form': form, 'edit_mode': True})


@admin_required
def delete_bank(request, pk):
    bank = get_object_or_404(Bank, pk=pk)
    if request.method == 'POST':
        bank.delete()
        messages.success(request, 'Bank deleted successfully.')
        return redirect('view_banks')
    return render(request, 'cases/delete_bank_confirm.html', {'bank': bank})


# Branch Views
@admin_required
def create_branch(request):
    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Branch created successfully.')
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
            messages.success(request, 'Branch updated successfully.')
            return redirect('view_branches')
    else:
        form = BranchForm(instance=branch)
    return render(request, 'cases/create_branch.html', {'form': form, 'edit_mode': True})


@admin_required
def delete_branch(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == 'POST':
        branch.delete()
        messages.success(request, 'Branch deleted successfully.')
        return redirect('view_branches')
    return render(request, 'cases/delete_branch_confirm.html', {'branch': branch})


# Branch Case Type Views
@admin_required
def assign_case_type(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == 'POST':
        form = BranchCaseTypeForm(request.POST)
        if form.is_valid():
            branch_case_type = form.save(commit=False)
            branch_case_type.branch = branch
            branch_case_type.save()
            messages.success(request, 'Case Type assigned to branch successfully.')
            return redirect('view_branches')
    else:
        form = BranchCaseTypeForm()
    return render(request, 'cases/assign_case_type.html', {'form': form, 'branch': branch})


@admin_required
def edit_branch_case_type(request, pk):
    branch_case_type = get_object_or_404(BranchCaseType, pk=pk)
    if request.method == 'POST':
        form = BranchCaseTypeForm(request.POST, instance=branch_case_type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Branch-Case Type association updated successfully.')
            return redirect('view_branches')
    else:
        form = BranchCaseTypeForm(instance=branch_case_type)
    return render(request, 'cases/assign_case_type.html', {
        'form': form,
        'branch': branch_case_type.branch,
        'edit_mode': True
    })


@admin_required
def delete_branch_case_type(request, pk):
    branch_case_type = get_object_or_404(BranchCaseType, pk=pk)
    if request.method == 'POST':
        branch_case_type.delete()
        messages.success(request, 'Branch-Case Type association deleted successfully.')
        return redirect('view_branches')
    return render(request, 'cases/delete_branch_case_type_confirm.html', {'branch_case_type': branch_case_type})
