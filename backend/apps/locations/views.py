"""API views for locations and categories reference endpoints (FR-05, SCR-04)."""

from drf_spectacular.utils import extend_schema
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

    @extend_schema(
        operation_id="api_locations_list",
        summary="List active locations",
        description="List active locations scoped to the caller's assigned residence (FR-05, SCR-04).",
        responses={200: LocationSerializer(many=True)},
    )
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

    @extend_schema(
        operation_id="api_categories_list",
        summary="List fault categories",
        description="List approved active fault categories in Moroka Hall (FR-05, SCR-04).",
        responses={200: FaultCategorySerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        categories = FaultCategory.objects.filter(is_active=True).order_by("name")
        serializer = FaultCategorySerializer(categories, many=True)
        return Response(serializer.data)
