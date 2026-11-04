from config.exceptions import ForbiddenException
from config.pagination import paginate, parse_int
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

        params = request.query_params
        qs = AuditService.search_events(
            actor_id=parse_int(params.get("actor_id")),
            action=params.get("action"),
            request_id=parse_int(params.get("request_id")),
            from_date=params.get("date_from"),
            to_date=params.get("date_to"),
            search=params.get("search"),
        )

        page, meta = paginate(request, qs)
        serializer = AuditEventItemSerializer(page, many=True)

        available_actions = [
            {"value": ch[0], "label": ch[1]} for ch in AuditAction.choices
        ]

        return Response(
            {
                **meta,
                "events": serializer.data,
                "available_actions": available_actions,
            },
            status=status.HTTP_200_OK,
        )
