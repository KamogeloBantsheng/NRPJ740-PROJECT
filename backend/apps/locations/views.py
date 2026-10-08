"""API views for locations and categories reference endpoints (FR-05, SCR-04)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.locations.models import FaultCategory, Location
from apps.locations.serializers import FaultCategorySerializer, LocationSerializer


class LocationListView(APIView):
    """List active locations scoped to the caller's residence."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        user = request.user
        qs = Location.objects.filter(is_active=True)

        # Scoping: Residents and Wardens see only locations within their assigned residence
        if user.role in (Role.RESIDENT, Role.WARDEN):
            if user.residence_id:
                qs = qs.filter(residence_id=user.residence_id)
            else:
                qs = qs.none()
        else:
            # Supervisors/Technicians/Admins may filter by residence if provided
            residence_id = request.query_params.get("residence_id")
            if residence_id:
                qs = qs.filter(residence_id=residence_id)

        serializer = LocationSerializer(qs, many=True)
        return Response(serializer.data)


class FaultCategoryListView(APIView):
    """List approved active fault categories."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        categories = FaultCategory.objects.filter(is_active=True).order_by("name")
        serializer = FaultCategorySerializer(categories, many=True)
        return Response(serializer.data)
