from config.exceptions import ForbiddenException
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.audit.models import AuditAction
from apps.audit.serializers import AuditEventItemSerializer
from apps.audit.services import AuditService


class AuditLogListView(APIView):
    """Global audit log search and inspection endpoint for administrators (FR-18, SCR-13, TC-41)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_audit_logs_list",
        summary="Search system audit logs",
        description="Global audit log search and inspection endpoint for administrators (FR-18, SCR-13, TC-41).",
        responses={
            200: inline_serializer(
                name="AuditLogSearchResponse",
                fields={
                    "total_count": serializers.IntegerField(),
                    "limit": serializers.IntegerField(),
                    "offset": serializers.IntegerField(),
                    "events": AuditEventItemSerializer(many=True),
                    "available_actions": serializers.ListField(child=serializers.DictField()),
                },
            )
        },
    )
    def get(self, request: Request) -> Response:
        if request.user.role != Role.ADMIN:
            raise ForbiddenException("Only administrators can access the system audit log.")

        # Parse query filters
        actor_id_raw = request.query_params.get("actor_id")
        actor_id = int(actor_id_raw) if actor_id_raw and actor_id_raw.isdigit() else None

        action = request.query_params.get("action")
        req_id_raw = request.query_params.get("request_id")
        request_id = int(req_id_raw) if req_id_raw and req_id_raw.isdigit() else None

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        search = request.query_params.get("search")

        # Pagination
        try:
            limit = min(200, max(1, int(request.query_params.get("limit", 50))))
        except (ValueError, TypeError):
            limit = 50

        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
        except (ValueError, TypeError):
            offset = 0

        qs = AuditService.search_events(
            actor_id=actor_id,
            action=action,
            request_id=request_id,
            from_date=date_from,
            to_date=date_to,
            search=search,
        )

        total_count = qs.count()
        paged_events = qs[offset : offset + limit]

        serializer = AuditEventItemSerializer(paged_events, many=True)

        available_actions = [
            {"value": ch[0], "label": ch[1]} for ch in AuditAction.choices
        ]

        return Response(
            {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "events": serializer.data,
                "available_actions": available_actions,
            },
            status=status.HTTP_200_OK,
        )
