from django.urls import path
from . import views

app_name = 'Bank'

urlpatterns = [
    path('create/', views.CreateBankView, name='createbank'),
    path('detail/<int:bank_id>/', views.BankDetailView, name='bank_detail'),
    path('delete/<int:bank_id>/', views.DeleteBankView, name='delete_bank'),
    path('states/<int:bank_id>/', views.ManageBankStatesView, name='manage_bank_states'),
    path('branches/<int:bank_id>/', views.ManageBankBranchesView, name='manage_bank_branches'),
    path('branches/<int:bank_id>/edit/<int:branch_id>/', views.EditBankBranchView, name='edit_bank_branch'),
    path('branches/<int:bank_id>/delete/<int:branch_id>/', views.DeleteBankBranchView, name='delete_bank_branch'),
    path('fees/<int:bank_id>/', views.ManageBankFeesView, name='manage_bank_fees'),
    path('documents/<int:bank_id>/', views.ManageBankDocumentsView, name='manage_bank_documents'),
    path('documents/<int:bank_id>/edit/<int:doc_id>/', views.EditBankDocumentView, name='edit_bank_document'),
    path('documents/<int:bank_id>/delete/<int:doc_id>/', views.DeleteBankDocumentView, name='delete_bank_document'),
    path('view/', views.ViewBanksView, name='viewbanks'),
]