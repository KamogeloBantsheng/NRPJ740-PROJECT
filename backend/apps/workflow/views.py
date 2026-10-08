"""API views for maintenance request lifecycle: submission, listing, detail, and timeline (FR-05, FR-06, FR-18)."""

import uuid

from config.exceptions import ForbiddenException, NotFoundException, ValidationException
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.audit.services import AuditService
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import MaintenanceRequest
from apps.workflow.permissions import PermissionPolicy
from apps.workflow.serializers import (
    MaintenanceRequestDetailSerializer,
    MaintenanceRequestListSerializer,
    RequestTimelineEventSerializer,
    SubmitRequestSerializer,
)
from apps.workflow.services import TransitionService


class RequestListCreateView(APIView):
    """List role-scoped requests or submit a new maintenance request (FR-05, FR-06)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        """Return role-scoped requests for the authenticated user (SCR-03, BR-05)."""
        qs = PermissionPolicy.scope_requests(request.user)

        # Optional filters
        req_status = request.query_params.get("status")
        if req_status:
            qs = qs.filter(status=req_status)

        category_id = request.query_params.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)

        serializer = MaintenanceRequestListSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        """Submit a new fault report under Table 5.1 T1 rules (SCR-04, FR-05)."""
        if request.user.role != Role.RESIDENT:
            raise ForbiddenException("Only residents can submit maintenance requests.")

        serializer = SubmitRequestSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationException(
                "Invalid request payload.",
                fields=serializer.errors,
            )

        data = serializer.validated_data
        location = Location.objects.get(id=data["location_id"])
        category = FaultCategory.objects.get(id=data["category_id"])

        # Check client_token from body or X-Client-Token header
        client_token = data.get("client_token")
        if not client_token:
            header_token = request.headers.get("X-Client-Token")
            if header_token:
                try:
                    client_token = uuid.UUID(header_token)
                except ValueError:
                    pass

        req, created = TransitionService.submit_request(
            resident=request.user,
            location=location,
            category=category,
            description=data["description"],
            client_token=client_token,
        )

        resp_serializer = MaintenanceRequestDetailSerializer(req)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(resp_serializer.data, status=status_code)


class RequestDetailView(APIView):
    """Retrieve full details of a specific maintenance request (SCR-05, FR-06)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, pk: int) -> Response:
        req = (
            MaintenanceRequest.objects.select_related(
                "resident", "location", "category", "location__residence"
            )
            .filter(id=pk)
            .first()
        )
        if not req or not PermissionPolicy.can_view_request(request.user, req):
            raise NotFoundException(f"Maintenance request {pk} not found or outside your scope.")

        serializer = MaintenanceRequestDetailSerializer(req)
        return Response(serializer.data)


class RequestTimelineView(APIView):
    """Retrieve chronological audit timeline for a maintenance request (FR-18, SCR-05)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, pk: int) -> Response:
        req = (
            MaintenanceRequest.objects.select_related("resident", "location")
            .filter(id=pk)
            .first()
        )
        if not req or not PermissionPolicy.can_view_request(request.user, req):
            raise NotFoundException(f"Maintenance request {pk} not found or outside your scope.")

        events = AuditService.get_request_history(req.id)
        serializer = RequestTimelineEventSerializer(events, many=True)
        return Response(serializer.data)
