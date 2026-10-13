"""URL routing for maintenance request workflow endpoints."""

from django.urls import path

from apps.workflow.views import (
    RequestDetailView,
    RequestListCreateView,
    RequestTimelineView,
    RequestTransitionView,
    TechnicianListView,
    TechnicianWorkQueueView,
)

urlpatterns = [
    path("requests/", RequestListCreateView.as_view(), name="request-list-create"),
    path("requests/<int:pk>/", RequestDetailView.as_view(), name="request-detail"),
    path("requests/<int:pk>/timeline/", RequestTimelineView.as_view(), name="request-timeline"),
    path("requests/<int:pk>/transition/", RequestTransitionView.as_view(), name="request-transition"),
    path("technicians/", TechnicianListView.as_view(), name="technician-list"),
    path("work-queue/", TechnicianWorkQueueView.as_view(), name="work-queue"),
]
