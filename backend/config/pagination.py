"""Shared query-parameter parsing and list pagination (Section 5.7: pagination capped at 50)."""

from typing import Any

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers
from rest_framework.request import Request

MAX_PAGE_SIZE = 50


def parse_int(value: Any, default: int | None = None) -> int | None:
    """Read an integer query parameter; anything else is ignored (ST-01), never a server error."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def paginate(request: Request, queryset) -> tuple[Any, dict[str, int]]:
    """Slice a queryset by limit and offset, and return the page with its metadata."""
    limit = min(MAX_PAGE_SIZE, max(1, parse_int(request.query_params.get("limit"), MAX_PAGE_SIZE)))
    offset = max(0, parse_int(request.query_params.get("offset"), 0))
    meta = {"total_count": queryset.count(), "limit": limit, "offset": offset}
    return queryset[offset : offset + limit], meta


def paged_response_schema(name: str, item_serializer, **extra_fields):
    """OpenAPI description of the paginated list envelope."""
    return inline_serializer(
        name=name,
        fields={
            "total_count": serializers.IntegerField(),
            "limit": serializers.IntegerField(),
            "offset": serializers.IntegerField(),
            "results": item_serializer(many=True),
            **extra_fields,
        },
    )
