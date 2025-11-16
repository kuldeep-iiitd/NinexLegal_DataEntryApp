from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path("", include("accounts.urls")),  # Root URL includes accounts URLs (landing page)
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("cases/", include("cases.urls")),
    path("billing/", include("billing.urls")),
    # Bank app (register namespace 'Bank' used by templates)
    path("bank/", include(("Bank.urls", "Bank"), namespace="Bank")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
