"""URL routing for maintenance request workflow endpoints."""

from django.urls import path

from apps.workflow.views import RequestDetailView, RequestListCreateView, RequestTimelineView

urlpatterns = [
    path("requests/", RequestListCreateView.as_view(), name="request-list-create"),
    path("requests/<int:pk>/", RequestDetailView.as_view(), name="request-detail"),
    path("requests/<int:pk>/timeline/", RequestTimelineView.as_view(), name="request-timeline"),
]
