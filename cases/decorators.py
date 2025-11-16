from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from functools import wraps
from .models import Employee

def admin_required(view_func):
    """Decorator that requires user to be in ADMIN or CO-ADMIN group"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Check if user is in ADMIN or CO-ADMIN groups or is superuser
        is_admin = request.user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or request.user.is_superuser
        
        if is_admin:
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, "You don't have administrative privileges to access this page.")
            return redirect('dashboard')
    
    return wrapper

def advocate_or_admin_required(view_func):
    """Decorator that requires user to be advocate, in ADMIN/CO-ADMIN group, or superuser"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Check if user is in ADMIN or CO-ADMIN groups or is superuser
        is_admin = request.user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or request.user.is_superuser
        
        if is_admin:
            return view_func(request, *args, **kwargs)
        
        # Check if user is an advocate
        try:
            employee = Employee.objects.get(user=request.user)
            if employee.employee_type == 'advocate':
                return view_func(request, *args, **kwargs)
        except Employee.DoesNotExist:
            pass
        
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard')
    
    return wrapper

def sro_or_admin_required(view_func):
    """Decorator that requires user to be SRO, in ADMIN/CO-ADMIN group, or superuser"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        # Admins always allowed
        is_admin = request.user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or request.user.is_superuser
        if is_admin:
            return view_func(request, *args, **kwargs)

        # Check if user is an SRO
        try:
            employee = Employee.objects.get(user=request.user)
            if employee.employee_type == 'sro':
                return view_func(request, *args, **kwargs)
        except Employee.DoesNotExist:
            pass

        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard')

    return wrapper

def get_user_employee(user):
    """Helper function to get employee object for a user"""
    try:
        return Employee.objects.get(user=user)
    except Employee.DoesNotExist:
        return None

def check_case_access(user, case):
    """Check if user has access to view/edit a case"""
    # Check if user is in ADMIN or CO-ADMIN groups or is superuser
    is_admin = user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or user.is_superuser
    
    if is_admin:
        return True
    
    employee = get_user_employee(user)
    if not employee:
        return False
    
    # Admin and SRO have access to all cases
    if employee.employee_type in ['admin', 'sro']:
        return True
    
    # Advocates can only access their assigned cases
    if employee.employee_type == 'advocate':
        return case.assigned_advocate == employee
    
    return False
