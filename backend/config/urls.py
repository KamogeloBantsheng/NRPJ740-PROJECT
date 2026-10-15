"""URL configuration for NPRJ740 Maintenance Request & Work-Order Management System.
Per Section 6.3: /api/health/ has a trailing slash.
"""
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .views import health_check

urlpatterns = [
    path("api/health/", health_check, name="health_check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.locations.urls")),
    path("api/", include("apps.workflow.urls")),
    path("api/", include("apps.audit.urls")),
]
