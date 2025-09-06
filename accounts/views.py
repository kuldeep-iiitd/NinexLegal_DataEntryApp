from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from cases.models import Employee, Case
from django.db.models import Q

@login_required
def dashboard(request):
    user = request.user
    
    # Check if user is in ADMIN or CO-ADMIN groups
    is_admin = user.groups.filter(name__in=['ADMIN', 'CO-ADMIN']).exists() or user.is_superuser
    
    # Check if user has an employee profile
    try:
        employee = Employee.objects.get(user=user)
        employee_id = employee.employee_id
        employee_type = employee.employee_type
        employee_name = employee.name
        
        # Debug: Print employee type and group status to console
        print(f"DEBUG: User {user.username} has employee_type: {employee_type}, is_admin: {is_admin}")
        
        # If user is an advocate and NOT in admin groups, show employee dashboard
        if employee_type == 'advocate' and not is_admin:
            # Get all cases assigned to this advocate
            assigned_cases = Case.objects.filter(assigned_advocate=employee).order_by('-created_at')
            
            # Calculate statistics
            total_cases = assigned_cases.count()
            active_cases = assigned_cases.filter(status__in=['on_hold', 'on_query']).count()
            pending_cases = assigned_cases.filter(status__in=['pending']).count()
            completed_cases = assigned_cases.filter(status__in=['positive', 'negative']).count()

            # Segmented lists for UI columns as requested
            # Section 1: Completed cases (positive and negative)
            completed_cases_list = assigned_cases.filter(status__in=['positive','negative'])
            
            # Section 2: Pending cases that haven't been worked on
            pending_cases_list = assigned_cases.filter(status='pending')
            
            # Section 3: Cases on hold, query, or with document pending
            hold_query_doc_cases_list = assigned_cases.filter(status__in=['on_hold', 'on_query', 'document_pending'])
            
            print(f"DEBUG: Advocate {employee_name} - Rendering employee_dashboard.html")
            
            return render(request, "accounts/employee_dashboard.html", {
                "username": user.username,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "employee_type": employee_type,
                "employee": employee,
                "assigned_cases": assigned_cases,
                "total_cases": total_cases,
                "active_cases": active_cases,
                "pending_cases": pending_cases,
                "completed_cases": completed_cases,
                "pending_cases_list": pending_cases_list,
                "hold_query_doc_cases_list": hold_query_doc_cases_list,
                "completed_cases_list": completed_cases_list,
            })
        else:
            # Admin, CO-ADMIN, or SRO - show admin dashboard with overall statistics
            total_cases = Case.objects.count()
            pending_cases = Case.objects.filter(status__in=['pending_assignment', 'document_pending']).count()
            assigned_cases = Case.objects.filter(assigned_advocate__isnull=False).count()
            total_advocates = Employee.objects.filter(employee_type='advocate', is_active=True).count()
            
            print(f"DEBUG: Admin/SRO {employee_name} - Rendering admin dashboard.html")
            
            context = {
                "username": user.username,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "employee_type": employee_type,
                "employee": employee,
                "total_cases": total_cases,
                "pending_cases": pending_cases,
                "assigned_cases": assigned_cases,
                "total_advocates": total_advocates,
                "is_admin": is_admin,
            }
            return render(request, "accounts/dashboard.html", context)
            
    except Employee.DoesNotExist:
        # Fallback for users without employee profile
        print(f"DEBUG: User {user.username} has no Employee profile - using fallback")
        
        # If user is in ADMIN/CO-ADMIN groups or is superuser, show admin dashboard
        if is_admin:
            messages.info(request, "Please create an Employee profile for yourself to access all features.")
            total_cases = Case.objects.count() if Case.objects.exists() else 0
            pending_cases = Case.objects.filter(status__in=['pending_assignment', 'document_pending']).count() if Case.objects.exists() else 0
            assigned_cases = Case.objects.filter(assigned_advocate__isnull=False).count() if Case.objects.exists() else 0
            total_advocates = Employee.objects.filter(employee_type='advocate', is_active=True).count()
            
            context = {
                "username": user.username,
                "employee_id": f"ADMIN-{user.id}",
                "total_cases": total_cases,
                "pending_cases": pending_cases,
                "assigned_cases": assigned_cases,
                "total_advocates": total_advocates,
                "is_admin": is_admin,
            }
            return render(request, "accounts/dashboard.html", context)
        else:
            # Regular user without admin privileges - show limited dashboard
            messages.warning(request, "You don't have administrative privileges. Contact admin for access.")
            context = {
                "username": user.username,
                "employee_id": user.id,
                "is_admin": False,
            }
            return render(request, "accounts/dashboard.html", context)
