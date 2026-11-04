"""API views for maintenance request lifecycle: submission, listing, detail, and timeline (FR-05, FR-06, FR-18)."""

import uuid

from config.exceptions import ForbiddenException, NotFoundException, ValidationException
from config.pagination import paged_response_schema, paginate, parse_int
from django.db.models import Case, Count, IntegerField, OuterRef, Q, QuerySet, Subquery, Value, When
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.permissions import IsSupervisor, IsTechnician
from apps.audit.services import AuditService
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import MaintenanceRequest, Priority, RequestStatus, WorkOrder
from apps.workflow.permissions import PermissionPolicy
from apps.workflow.serializers import (
    MaintenanceRequestDetailSerializer,
    MaintenanceRequestListSerializer,
    RequestTimelineEventSerializer,
    SubmitRequestSerializer,
    TechnicianItemSerializer,
    TransitionExecuteSerializer,
)
from apps.workflow.services import ReportingService, TransitionService


def request_page_schema(name: str):
    """OpenAPI description of a page of requests with its per-status totals."""
    return paged_response_schema(
        name,
        MaintenanceRequestListSerializer,
        status_totals=serializers.DictField(child=serializers.IntegerField()),
    )


def apply_request_filters(request: Request, queryset: QuerySet) -> QuerySet:
    """Filters shared by the request lists. Bad values are ignored, never a server error (ST-01)."""
    params = request.query_params

    if params.get("mine", "").lower() in ("true", "1"):
        queryset = queryset.filter(resident=request.user)

    for parameter, field in (
        ("category_id", "category_id"),
        ("location_id", "location_id"),
        ("residence_id", "location__residence_id"),
    ):
        value = parse_int(params.get(parameter))
        if value is not None:
            queryset = queryset.filter(**{field: value})

    search = params.get("search", "").strip()
    if search:
        matches = Q(description__icontains=search) | Q(location__label__icontains=search)
        tracking_digits = search.upper().removeprefix("MR-")
        if tracking_digits.isdecimal():
            matches |= Q(id=int(tracking_digits))
        # Only roles allowed to see resident identity may search by it (BR-04)
        if request.user.role == Role.SUPERVISOR:
            matches |= Q(resident__full_name__icontains=search)
        queryset = queryset.filter(matches)

    return queryset


def status_filter(request: Request) -> list[str]:
    return [item.strip() for item in request.query_params.get("status", "").split(",") if item.strip()]


def status_totals(queryset: QuerySet) -> dict[str, int]:
    """Totals per status across every page, for the counters above a list."""
    return dict(queryset.order_by().values_list("status").annotate(total=Count("id")))


def paged_requests(request: Request, queryset: QuerySet, statuses: list[str]) -> Response:
    """Serialize one page of requests with the totals the list screens display."""
    totals = status_totals(queryset)
    if statuses:
        queryset = queryset.filter(status__in=statuses)

    page, meta = paginate(request, queryset)
    serializer = MaintenanceRequestListSerializer(page, many=True, context={"request": request})
    return Response({**meta, "status_totals": totals, "results": serializer.data})


class RequestListCreateView(APIView):
    """List role-scoped requests or submit a new maintenance request (FR-05, FR-06)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_requests_list",
        summary="List maintenance requests",
        description="Return role-scoped requests for the authenticated user (SCR-03, BR-05).",
        responses={200: request_page_schema("PagedRequests")},
    )
    def get(self, request: Request) -> Response:
        """Return role-scoped requests for the authenticated user (SCR-03, BR-05)."""
        queryset = apply_request_filters(request, PermissionPolicy.scope_requests(request.user))
        return paged_requests(request, queryset, status_filter(request))

    @extend_schema(
        operation_id="api_requests_create",
        summary="Submit maintenance request",
        description="Submit a new fault report under Table 5.1 T1 rules (SCR-04, FR-05).",
        request=SubmitRequestSerializer,
        responses={
            201: MaintenanceRequestDetailSerializer,
            200: MaintenanceRequestDetailSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        """Submit a new fault report under Table 5.1 T1 rules (SCR-04, FR-05)."""
        if request.user.role not in (Role.RESIDENT, Role.WARDEN):
            raise ForbiddenException("Only residents and residence wardens can submit maintenance requests.")

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

        resp_serializer = MaintenanceRequestDetailSerializer(req, context={"request": request})
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(resp_serializer.data, status=status_code)


class RequestDetailView(APIView):
    """Retrieve full details of a specific maintenance request (SCR-05, FR-06)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_requests_retrieve",
        summary="Retrieve maintenance request details",
        description="Retrieve full details of a specific maintenance request (SCR-05, FR-06).",
        responses={200: MaintenanceRequestDetailSerializer},
    )
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

    @extend_schema(
        operation_id="api_requests_timeline",
        summary="Retrieve request audit timeline",
        description="Retrieve chronological audit timeline for a maintenance request (FR-18, SCR-05).",
        responses={200: RequestTimelineEventSerializer(many=True)},
    )
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

    @extend_schema(
        operation_id="api_requests_transition",
        summary="Execute request lifecycle transition",
        description="Execute a lifecycle state transition with row lock and concurrency guard (Table 5.1, ADR-02).",
        request=TransitionExecuteSerializer,
        responses={200: MaintenanceRequestDetailSerializer},
    )
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


class TriageQueueView(APIView):
    """Requests waiting for a triage decision, oldest first (FR-08, SCR-06)."""

    permission_classes = (IsAuthenticated, IsSupervisor)

    @extend_schema(
        operation_id="api_triage_queue_list",
        summary="List the triage queue",
        description=(
            "Submitted requests, oldest first, at most 50 per page, filterable by residence and "
            "category (FR-08, SCR-06). Pass status to include other states."
        ),
        responses={200: request_page_schema("PagedTriageQueue")},
    )
    def get(self, request: Request) -> Response:
        queryset = apply_request_filters(request, PermissionPolicy.scope_requests(request.user))
        return paged_requests(
            request,
            queryset.order_by("created_at", "id"),
            status_filter(request) or [RequestStatus.SUBMITTED],
        )


class TechnicianListView(APIView):
    """List active technicians with workload counts for supervisor dispatch (SCR-07, FR-10, FR-11)."""

    permission_classes = (IsAuthenticated, IsSupervisor)

    @extend_schema(
        operation_id="api_technicians_list",
        summary="List active technicians for dispatch",
        description="List active technicians with workload counts for supervisor dispatch (SCR-07, FR-10, FR-11).",
        responses={200: TechnicianItemSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
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

    permission_classes = (IsAuthenticated, IsTechnician)

    # Finished work leaves the queue until a Supervisor reopens it (AC-15.1)
    ACTIVE_STATUSES = (RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS, RequestStatus.REOPENED)

    @extend_schema(
        operation_id="api_work_queue_list",
        summary="List assigned technician work orders",
        description=(
            "Active work assigned to the authenticated technician, by priority and then assignment "
            "time (FR-13, SCR-09, BR-04). Pass status=WORK_COMPLETED to see work awaiting verification."
        ),
        responses={200: request_page_schema("PagedWorkQueue")},
    )
    def get(self, request: Request) -> Response:
        queryset = apply_request_filters(request, PermissionPolicy.scope_requests(request.user))

        priority_rank = Case(
            When(priority=Priority.CRITICAL, then=Value(1)),
            When(priority=Priority.HIGH, then=Value(2)),
            When(priority=Priority.MEDIUM, then=Value(3)),
            When(priority=Priority.LOW, then=Value(4)),
            default=Value(5),
            output_field=IntegerField(),
        )
        assigned_at = WorkOrder.objects.filter(request=OuterRef("pk"), ended_at__isnull=True).values("assigned_at")[:1]
        queryset = queryset.annotate(_priority_rank=priority_rank, _assigned_at=Subquery(assigned_at)).order_by(
            "_priority_rank", "_assigned_at"
        )

        return paged_requests(request, queryset, status_filter(request) or list(self.ACTIVE_STATUSES))


class DashboardView(APIView):
    """Operational dashboard providing role-scoped maintenance aggregates (FR-16, SCR-10, BR-04, NFR-06).

    - Warden: strictly scoped to own residence, no resident personal data (TC-36).
    - Supervisor: all residences or filtered by residence_id (TC-37).
    - Every other role: forbidden (HTTP 403).
    - Read-only: mutation attempts return HTTP 403 (TC-36).
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_dashboard_metrics",
        summary="Operational dashboard metrics",
        description="Role-scoped maintenance aggregates for Supervisor and Warden (FR-16, SCR-10).",
        responses={
            200: inline_serializer(
                name="DashboardMetricsResponse",
                fields={
                    "scope": serializers.DictField(),
                    "summary": serializers.DictField(),
                    "status_counts": serializers.DictField(child=serializers.IntegerField()),
                    "priority_counts": serializers.DictField(child=serializers.IntegerField()),
                    "category_counts": serializers.ListField(child=serializers.DictField()),
                    "aging_distribution": serializers.DictField(child=serializers.IntegerField()),
                },
            )
        },
    )
    def get(self, request: Request) -> Response:
        metrics = ReportingService.get_dashboard_metrics(
            user=request.user,
            residence_id=parse_int(request.query_params.get("residence_id")),
        )
        return Response(metrics, status=status.HTTP_200_OK)

    @extend_schema(exclude=True)
    def post(self, request: Request) -> Response:
        raise ForbiddenException("The operational dashboard is strictly read-only.")

    @extend_schema(exclude=True)
    def put(self, request: Request) -> Response:
        raise ForbiddenException("The operational dashboard is strictly read-only.")

    @extend_schema(exclude=True)
    def patch(self, request: Request) -> Response:
        raise ForbiddenException("The operational dashboard is strictly read-only.")

    @extend_schema(exclude=True)
    def delete(self, request: Request) -> Response:
        raise ForbiddenException("The operational dashboard is strictly read-only.")



