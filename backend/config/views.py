from django.db import DatabaseError, connection
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint: verifies application runtime and PostgreSQL connectivity."""
    db_status = "connected"
    http_status = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as exc:
        db_status = f"unhealthy: {exc}"
        http_status = 503

    return JsonResponse(
        {
            "status": "ok" if http_status == 200 else "degraded",
            "database": db_status,
        },
        status=http_status,
    )
