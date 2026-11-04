"""API views for residences, locations and categories reference endpoints (FR-05, SCR-04)."""

from config.pagination import parse_int
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import IsSupervisorOrAdmin
from apps.locations.models import FaultCategory, Location, LocationKind, Residence
from apps.locations.serializers import FaultCategorySerializer, LocationSerializer, ResidenceSerializer


class ResidenceListView(APIView):
    """List active residences for the Supervisor queue filter and Admin user forms (FR-03, FR-08)."""

    permission_classes = (IsAuthenticated, IsSupervisorOrAdmin)

    @extend_schema(
        operation_id="api_residences_list",
        summary="List active residences",
        description="List active residences for the triage filter and user administration (FR-03, FR-08).",
        responses={200: ResidenceSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        serializer = ResidenceSerializer(Residence.objects.filter(is_active=True), many=True)
        return Response(serializer.data)


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

        # Scoping per user role:
        # Residents see strictly their assigned room plus common areas in their residence
        if user.role == Role.RESIDENT:
            if user.residence_id:
                resident_filter = Q(residence_id=user.residence_id, kind=LocationKind.COMMON_AREA)
                if user.assigned_location_id:
                    resident_filter |= Q(id=user.assigned_location_id)
                qs = qs.filter(resident_filter)
            else:
                qs = qs.none()
        # Wardens can choose from all rooms and common areas in their residence
        elif user.role == Role.WARDEN:
            if user.residence_id:
                qs = qs.filter(residence_id=user.residence_id)
            else:
                qs = qs.none()
        else:
            # Supervisors/Technicians/Admins may filter by residence if provided
            residence_id = parse_int(request.query_params.get("residence_id"))
            if residence_id is not None:
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
