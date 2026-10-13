"""API views for maintenance request lifecycle: submission, listing, detail, and timeline (FR-05, FR-06, FR-18)."""

import uuid

from config.exceptions import ForbiddenException, NotFoundException, ValidationException
from django.db.models import Case, Count, IntegerField, Q, Value, When
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.audit.services import AuditService
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import MaintenanceRequest, Priority
from apps.workflow.permissions import PermissionPolicy
from apps.workflow.serializers import (
    MaintenanceRequestDetailSerializer,
    MaintenanceRequestListSerializer,
    RequestTimelineEventSerializer,
    SubmitRequestSerializer,
    TechnicianItemSerializer,
    TransitionExecuteSerializer,
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
            statuses = [s.strip() for s in req_status.split(",") if s.strip()]
            if len(statuses) == 1:
                qs = qs.filter(status=statuses[0])
            elif len(statuses) > 1:
                qs = qs.filter(status__in=statuses)

        category_id = request.query_params.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)

        location_id = request.query_params.get("location_id")
        if location_id:
            qs = qs.filter(location_id=location_id)

        serializer = MaintenanceRequestListSerializer(
            qs,
            many=True,
            context={"request": request},
        )
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

        serializer = MaintenanceRequestDetailSerializer(req, context={"request": request})
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
        serializer = RequestTimelineEventSerializer(
            events,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)


class RequestTransitionView(APIView):
    """Execute a lifecycle state transition with row lock and concurrency guard (Table 5.1, ADR-02)."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request, pk: int) -> Response:
        req = (
            MaintenanceRequest.objects.select_related(
                "resident", "location", "category", "location__residence"
            )
            .filter(id=pk)
            .first()
        )
        if not req or not PermissionPolicy.can_view_request(request.user, req):
            raise NotFoundException(f"Maintenance request {pk} not found or outside your scope.")

        serializer = TransitionExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationException(
                "Invalid transition payload.",
                fields=serializer.errors,
            )

        data = serializer.validated_data
        updated_req = TransitionService.execute(
            request_id=pk,
            action=data["action"],
            actor=request.user,
            expected_status=data["expected_status"],
            payload={
                "note": data.get("note", ""),
                "priority": data.get("priority"),
                "technician_id": data.get("technician_id"),
            },
        )

        resp_serializer = MaintenanceRequestDetailSerializer(
            updated_req,
            context={"request": request},
        )
        return Response(resp_serializer.data, status=status.HTTP_200_OK)


class TechnicianListView(APIView):
    """List active technicians with workload counts for supervisor dispatch (SCR-07, FR-10, FR-11)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        if request.user.role not in (Role.SUPERVISOR, Role.ADMIN):
            raise ForbiddenException("Only supervisors and admins can view technician dispatch availability.")

        technicians = (
            User.objects.filter(role=Role.TECHNICIAN, is_active=True)
            .annotate(
                active_tasks_count=Count(
                    "work_orders",
                    filter=Q(work_orders__ended_at__isnull=True),
                )
            )
            .order_by("full_name")
        )
        serializer = TechnicianItemSerializer(technicians, many=True)
        return Response(serializer.data)


class TechnicianWorkQueueView(APIView):
    """List requests currently assigned to the authenticated technician (FR-13, SCR-09, BR-04)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        if request.user.role != Role.TECHNICIAN:
            raise ForbiddenException("Only technicians can view their assigned work queue.")

        qs = PermissionPolicy.scope_requests(request.user)

        # Optional status filtering (e.g. ASSIGNED, IN_PROGRESS, REOPENED)
        req_status = request.query_params.get("status")
        if req_status:
            statuses = [s.strip() for s in req_status.split(",") if s.strip()]
            if len(statuses) == 1:
                qs = qs.filter(status=statuses[0])
            elif len(statuses) > 1:
                qs = qs.filter(status__in=statuses)

        category_id = request.query_params.get("category_id")
        if category_id:
            qs = qs.filter(category_id=category_id)

        location_id = request.query_params.get("location_id")
        if location_id:
            qs = qs.filter(location_id=location_id)

        # Priority ordering: CRITICAL > HIGH > MEDIUM > LOW, then oldest report first
        priority_order = Case(
            When(priority=Priority.CRITICAL, then=Value(1)),
            When(priority=Priority.HIGH, then=Value(2)),
            When(priority=Priority.MEDIUM, then=Value(3)),
            When(priority=Priority.LOW, then=Value(4)),
            default=Value(5),
            output_field=IntegerField(),
        )
        qs = qs.annotate(_priority_rank=priority_order).order_by("_priority_rank", "created_at")

        serializer = MaintenanceRequestListSerializer(
            qs,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data)

