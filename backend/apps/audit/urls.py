"""URL routing for audit trail inspection endpoints."""

from django.urls import path

from apps.audit.views import AuditLogListView

urlpatterns = [
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),
    path("audit-logs", AuditLogListView.as_view(), name="audit-log-list-noslash"),
]
