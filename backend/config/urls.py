"""URL configuration for NPRJ740 Maintenance Request & Work-Order Management System.
Per Section 6.3: /api/health/ has a trailing slash.
"""
from django.urls import include, path

from .views import health_check

urlpatterns = [
    path("api/health/", health_check, name="health_check"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.locations.urls")),
    path("api/", include("apps.workflow.urls")),
]
