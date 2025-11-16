from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='billing_dashboard'),
    path('billing/', views.billing_view, name='billing_view'),
    path('mis/', views.mis_view, name='mis_view'),  # placeholder
    path('api/case-search/', views.case_search_api, name='billing_case_search_api'),
    path('api/update-fees/', views.update_fees_api, name='billing_update_fees_api'),
]
