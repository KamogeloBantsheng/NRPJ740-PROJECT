from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(
    operation_id="api_health_check",
    summary="Health check endpoint",
    description="Verifies application runtime and PostgreSQL database connectivity (NFR-09).",
    responses={
        200: inline_serializer(
            name="HealthCheckResponse",
            fields={
                "status": serializers.CharField(),
                "database": serializers.CharField(),
            },
        ),
        503: inline_serializer(
            name="HealthCheckDegradedResponse",
            fields={
                "status": serializers.CharField(),
                "database": serializers.CharField(),
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint: verifies application runtime and PostgreSQL connectivity."""
    db_status = "connected"
    http_status = status.HTTP_200_OK
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as exc:
        db_status = f"unhealthy: {exc}"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    return Response(
        {
            "status": "ok" if http_status == status.HTTP_200_OK else "degraded",
            "database": db_status,
        },
        status=http_status,
    )

