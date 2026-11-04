"""URL routing for maintenance request workflow endpoints."""

from django.urls import path

from apps.workflow.views import (
    DashboardView,
    RequestDetailView,
    RequestListCreateView,
    RequestTimelineView,
    RequestTransitionView,
    TechnicianListView,
    TechnicianWorkQueueView,
    TriageQueueView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("requests/", RequestListCreateView.as_view(), name="request-list-create"),
    path("requests/<int:pk>/", RequestDetailView.as_view(), name="request-detail"),
    path("requests/<int:pk>/timeline/", RequestTimelineView.as_view(), name="request-timeline"),
    path("requests/<int:pk>/transition/", RequestTransitionView.as_view(), name="request-transition"),
    path("triage-queue/", TriageQueueView.as_view(), name="triage-queue"),
    path("technicians/", TechnicianListView.as_view(), name="technician-list"),
    path("work-queue/", TechnicianWorkQueueView.as_view(), name="work-queue"),
]
