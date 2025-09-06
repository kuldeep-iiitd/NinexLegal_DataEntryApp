from django.urls import path
from . import views
from . import employee_views

urlpatterns = [
    # Cases Management
    path('create-case/', views.create_case, name='create_case'),
    path('view-cases/', views.view_cases, name='view_cases'),
    path('my-cases/<str:filter_type>/', views.advocate_cases_filtered, name='advocate_cases_filtered'),
    path('view-pending-cases/', views.view_pending_cases, name='view_pending_cases'),
    path('assign-case-advocate/<int:case_id>/', views.assign_case_advocate, name='assign_case_advocate'),
    path('case-detail/<int:case_id>/', views.case_detail, name='case_detail'),
    path('case-work/<int:case_id>/', views.work_on_case, name='work_on_case'),
    path('case-action/<int:case_id>/', views.case_action, name='case_action'),
    path('delete-case/<int:case_id>/', views.delete_case, name='delete_case'),
    
    # Case Types
    path('create-case-type/', views.create_case_type, name='create_case_type'),
    path('view-case-types/', views.view_case_types, name='view_case_types'),
    path('delete-case-type/<int:pk>/', views.delete_case_type, name='delete_case_type'),
    
    # Banks
    path('create-bank/', views.create_bank, name='create_bank'),
    path('view-banks/', views.view_banks, name='view_banks'),
    path('edit-bank/<int:pk>/', views.edit_bank, name='edit_bank'),
    path('delete-bank/<int:pk>/', views.delete_bank, name='delete_bank'),
    
    # Branches
    path('create-branch/', views.create_branch, name='create_branch'),
    path('view-branches/', views.view_branches, name='view_branches'),
    path('view-branches-by-bank/<int:pk>/', views.view_branches_by_bank, name='view_branches_by_bank'),
    path('edit-branch/<int:pk>/', views.edit_branch, name='edit_branch'),
    path('delete-branch/<int:pk>/', views.delete_branch, name='delete_branch'),
    
    # Branch Case Types
    path('assign-case-type/<int:pk>/', views.assign_case_type, name='assign_case_type'),
    path('edit-branch-case-type/<int:pk>/', views.edit_branch_case_type, name='edit_branch_case_type'),
    path('delete-branch-case-type/<int:pk>/', views.delete_branch_case_type, name='delete_branch_case_type'),
    
    # Employees
    path('create-employee/', employee_views.create_employee, name='create_employee'),
    path('view-employees/', employee_views.view_employees, name='view_employees'),
    path('edit-employee/<int:pk>/', employee_views.edit_employee, name='edit_employee'),
    path('delete-employee/<int:pk>/', employee_views.delete_employee, name='delete_employee'),
]
