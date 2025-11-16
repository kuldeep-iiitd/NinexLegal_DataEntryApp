from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.forms import modelformset_factory
from .models import Employee, EmployeeDocument
from .forms import EmployeeForm, EmployeeEditForm, EmployeeDocumentFormSet
from .decorators import admin_required

@admin_required
def create_employee(request):
    from django.contrib import messages
    DocumentFormSet = modelformset_factory(EmployeeDocument, fields=('name', 'file'), extra=1, can_delete=True)
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        document_formset = DocumentFormSet(request.POST, request.FILES, prefix='document', queryset=EmployeeDocument.objects.none())
        
        if form.is_valid() and document_formset.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            # Create Django user
            user = User.objects.create_user(
                username=username,
                password=password,
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['name']
            )
            
            # Create Employee profile
            employee = form.save(commit=False)
            employee.user = user
            employee.save()
            
            # Save documents
            for doc_form in document_formset:
                if doc_form.cleaned_data and not doc_form.cleaned_data.get('DELETE', False):
                    name = doc_form.cleaned_data.get('name')
                    file = doc_form.cleaned_data.get('file')
                    if name and file:
                        EmployeeDocument.objects.create(employee=employee, name=name, file=file)
            
            messages.success(request, f'Employee {employee.name} created successfully.')
            return redirect('view_employees')
        else:
            # Add error messages for debugging
            if not form.is_valid():
                messages.error(request, 'Please fix the form errors below.')
            if not document_formset.is_valid():
                messages.error(request, 'Please fix the document form errors.')
    else:
        form = EmployeeForm()
        document_formset = DocumentFormSet(prefix='document', queryset=EmployeeDocument.objects.none())
    
    return render(request, 'cases/create_employee.html', {
        'form': form,
        'document_formset': document_formset
    })

@admin_required
def view_employees(request):
    employees = Employee.objects.select_related('user').all()
    return render(request, 'cases/view_employees.html', {'employees': employees})

@admin_required
def edit_employee(request, pk):
    from django.contrib import messages
    employee = get_object_or_404(Employee, pk=pk)
    DocumentFormSet = modelformset_factory(EmployeeDocument, fields=('name', 'file'), extra=1, can_delete=True)
    if request.method == 'POST':
        form = EmployeeEditForm(request.POST, instance=employee)
        document_formset = DocumentFormSet(request.POST, request.FILES, prefix='document', queryset=EmployeeDocument.objects.filter(employee=employee))
        if form.is_valid() and document_formset.is_valid():
            # Update employee
            employee = form.save()
            
            # Update user account if needed
            if hasattr(employee, 'user') and employee.user:
                user = employee.user
                user.username = form.cleaned_data['username']
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['name']
                
                # Update password if provided
                password = form.cleaned_data.get('password')
                if password:
                    user.set_password(password)
                
                user.save()
            
            # Handle document formset
            for doc_form in document_formset:
                if doc_form.cleaned_data:
                    if doc_form.cleaned_data.get('DELETE', False):
                        if doc_form.instance.pk:
                            doc_form.instance.delete()
                    else:
                        name = doc_form.cleaned_data.get('name')
                        file = doc_form.cleaned_data.get('file')
                        if name and file:
                            if doc_form.instance.pk:
                                # Update existing document
                                doc_form.instance.name = name
                                if file:
                                    doc_form.instance.file = file
                                doc_form.instance.save()
                            else:
                                # Create new document
                                EmployeeDocument.objects.create(employee=employee, name=name, file=file)
            
            messages.success(request, f'Employee {employee.name} updated successfully.')
            return redirect('view_employees')
        else:
            if not form.is_valid():
                messages.error(request, 'Please fix the form errors below.')
            if not document_formset.is_valid():
                messages.error(request, 'Please fix the document form errors.')
    else:
        form = EmployeeEditForm(instance=employee)
        document_formset = DocumentFormSet(prefix='document', queryset=EmployeeDocument.objects.filter(employee=employee))
    return render(request, 'cases/edit_employee.html', {
        'form': form,
        'employee': employee,
        'document_formset': document_formset
    })

@admin_required
def delete_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        # Delete associated user account too
        if employee.user:
            employee.user.delete()  # This will cascade delete the employee through OneToOneField
        return redirect('view_employees')
    return render(request, 'cases/delete_employee_confirm.html', {'employee': employee})
