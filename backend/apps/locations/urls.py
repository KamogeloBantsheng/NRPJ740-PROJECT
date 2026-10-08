"""URL routing for locations and fault categories reference endpoints."""

from django.urls import path

from apps.locations.views import FaultCategoryListView, LocationListView

urlpatterns = [
    path("locations/", LocationListView.as_view(), name="location-list"),
    path("categories/", FaultCategoryListView.as_view(), name="category-list"),
]
