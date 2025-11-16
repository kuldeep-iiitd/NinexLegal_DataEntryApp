from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path("", TemplateView.as_view(template_name="accounts/landing.html"), name="landing"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("statistics/", views.admin_statistics, name="admin_statistics"),
    path("cases-by-status/<str:status>/", views.cases_by_status, name="cases_by_status"),
    path("cases-by-advocate/<int:advocate_id>/", views.cases_by_advocate, name="cases_by_advocate"),
    path("cases-by-bank/<int:bank_id>/", views.cases_by_bank, name="cases_by_bank"),
    path("generate-mis/", views.generate_mis, name="generate_mis"),
]
