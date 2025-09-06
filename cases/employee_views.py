from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Employee
from .forms import EmployeeForm, EmployeeEditForm
from .decorators import admin_required

@admin_required
def create_employee(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
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
            
            return redirect('view_employees')
    else:
        form = EmployeeForm()
    return render(request, 'cases/create_employee.html', {'form': form})

@admin_required
def view_employees(request):
    employees = Employee.objects.select_related('user').all()
    return render(request, 'cases/view_employees.html', {'employees': employees})

@admin_required
def edit_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeEditForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            return redirect('view_employees')
    else:
        form = EmployeeEditForm(instance=employee)
    return render(request, 'cases/edit_employee.html', {'form': form, 'employee': employee})

@admin_required
def delete_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        # Delete associated user account too
        if employee.user:
            employee.user.delete()  # This will cascade delete the employee through OneToOneField
        return redirect('view_employees')
    return render(request, 'cases/delete_employee_confirm.html', {'employee': employee})
