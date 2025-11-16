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
    path('reassign-case-advocate/<int:case_id>/', views.reassign_case_advocate, name='reassign_case_advocate'),
    path('case-detail/<int:case_id>/', views.case_detail, name='case_detail'),
    path('case-work/<int:case_id>/', views.work_on_case, name='work_on_case'),
    path('case-add-work/<int:case_id>/', views.add_case_work, name='add_case_work'),
    path('case-action/<int:case_id>/', views.case_action, name='case_action'),
    path('case-put-on-hold/<int:case_id>/', views.case_put_on_hold, name='case_put_on_hold'),
    path('case-upload/<int:case_id>/', views.case_upload_document, name='case_upload_document'),
    path('case-upload-group/<int:case_id>/', views.case_upload_documents_group, name='case_upload_documents_group'),
    path('case-finalize-with-document/<int:case_id>/', views.case_finalize_with_document, name='case_finalize_with_document'),
    path('post-finalize/<int:case_id>/', views.post_finalize_options, name='post_finalize_options'),
    path('add-child-case/<int:case_id>/', views.add_child_case, name='add_child_case'),
    path('delete-case/<int:case_id>/', views.delete_case, name='delete_case'),
    path('finalize-quotation/<int:case_id>/', views.finalize_quotation, name='finalize_quotation'),
    
    # Case Types
    path('create-case-type/', views.create_case_type, name='create_case_type'),
    path('view-case-types/', views.view_case_types, name='view_case_types'),
    path('delete-case-type/<int:pk>/', views.delete_case_type, name='delete_case_type'),
    
    # Banks
    path('create-bank/', views.create_bank, name='create_bank'),
    path('view-banks/', views.view_banks, name='view_banks'),
    path('api/banks/search/', views.search_banks, name='search_banks'),
    # Locations suggestions
    path('api/locations/states/', views.suggest_states, name='suggest_states'),
    path('api/locations/districts/', views.suggest_districts, name='suggest_districts'),
    path('api/locations/tehsils/', views.suggest_tehsils, name='suggest_tehsils'),
    path('bank-detail/<int:pk>/', views.view_bank_detail, name='view_bank_detail'),
    path('edit-bank/<int:pk>/', views.edit_bank, name='edit_bank'),
    path('delete-bank/<int:pk>/', views.delete_bank, name='delete_bank'),
    
    # Branches
    path('create-branch/', views.create_branch, name='create_branch'),
    path('view-branches/', views.view_branches, name='view_branches'),
    path('view-branches-by-bank/<int:pk>/', views.view_branches_by_bank, name='view_branches_by_bank'),
    path('edit-branch/<int:pk>/', views.edit_branch, name='edit_branch'),
    path('delete-branch/<int:pk>/', views.delete_branch, name='delete_branch'),
    
    
    # Employees
    path('create-employee/', employee_views.create_employee, name='create_employee'),
    path('view-employees/', employee_views.view_employees, name='view_employees'),
    path('employee-detail/<int:pk>/', views.view_employee_detail, name='view_employee_detail'),
    path('edit-employee/<int:pk>/', employee_views.edit_employee, name='edit_employee'),
    path('delete-employee/<int:pk>/', employee_views.delete_employee, name='delete_employee'),

    # SRO Dashboard
    path('sro/', views.sro_dashboard, name='sro_dashboard'),
    path('sro/case/<int:case_id>/', views.sro_case_detail, name='sro_case_detail'),
    path('sro/update/<int:case_id>/', views.sro_update_case, name='sro_update_case'),
    path('sro/update-group/<int:case_id>/', views.sro_update_group, name='sro_update_group'),
    # SRO management (admin)
    path('sro/manage/', views.sro_manage, name='sro_manage'),
    path('sro/manage/<int:pk>/', views.sro_manage_edit, name='sro_manage_edit'),

    # Location management (admin)
    path('locations/states/', views.locations_states_list, name='locations_states_list'),
    path('locations/states/add/', views.locations_state_create, name='locations_state_create'),
    path('locations/states/<int:pk>/edit/', views.locations_state_edit, name='locations_state_edit'),
    path('locations/states/<int:pk>/delete/', views.locations_state_delete, name='locations_state_delete'),

    path('locations/districts/', views.locations_districts_list, name='locations_districts_list'),
    path('locations/districts/add/', views.locations_district_create, name='locations_district_create'),
    path('locations/districts/<int:pk>/edit/', views.locations_district_edit, name='locations_district_edit'),
    path('locations/districts/<int:pk>/delete/', views.locations_district_delete, name='locations_district_delete'),

    path('locations/tehsils/', views.locations_tehsils_list, name='locations_tehsils_list'),
    path('locations/tehsils/add/', views.locations_tehsil_create, name='locations_tehsil_create'),
    path('locations/tehsils/<int:pk>/edit/', views.locations_tehsil_edit, name='locations_tehsil_edit'),
    path('locations/tehsils/<int:pk>/delete/', views.locations_tehsil_delete, name='locations_tehsil_delete'),
]
