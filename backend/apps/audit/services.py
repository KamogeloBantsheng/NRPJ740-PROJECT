"""AuditService implementation for recording and querying append-only audit events (FR-17, FR-18, NFR-05)."""

from datetime import timedelta
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent


class AuditService:
    """Encapsulates all audit trail operations inside the caller's transaction."""

    @staticmethod
    def record(
        action: AuditAction | str,
        *,
        actor: User | None = None,
        target_user: User | None = None,
        request_id: int | None = None,
        work_order_id: int | None = None,
        from_status: str | None = None,
        to_status: str | None = None,
        note: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Create and persist an append-only audit event.

        Must be called within an active transaction if part of a state transition.
        """
        if details is None:
            details = {}

        return AuditEvent.objects.create(
            action=action,
            actor=actor,
            target_user=target_user,
            request_id=request_id,
            work_order_id=work_order_id,
            from_status=from_status,
            to_status=to_status,
            note=note,
            details=details,
        )

    @staticmethod
    def get_request_history(request_id: int) -> QuerySet[AuditEvent]:
        """Return all audit events for a given request in chronological order for timeline display (FR-18)."""
        return (
            AuditEvent.objects.filter(request_id=request_id)
            .select_related("actor", "target_user")
            .order_by("occurred_at", "id")
        )

    @staticmethod
    def count_failed_logins(
        email: str | None = None,
        ip_address: str | None = None,
        *,
        window_seconds: int = 60,
    ) -> int:
        """Count failed sign-in attempts within a sliding window for DB-driven throttling (BR-07, Section 4.4)."""
        cutoff = timezone.now() - timedelta(seconds=window_seconds)
        queryset = AuditEvent.objects.filter(
            action=AuditAction.LOGIN_FAILED,
            occurred_at__gte=cutoff,
        )

        filter_condition = Q()
        if email:
            normalized_email = email.strip().lower()
            filter_condition |= Q(details__email=normalized_email)
        if ip_address:
            filter_condition |= Q(details__ip_address=ip_address.strip())

        if not filter_condition:
            return 0

        return queryset.filter(filter_condition).count()

    @staticmethod
    def search_events(
        *,
        actor_id: int | None = None,
        action: str | None = None,
        request_id: int | None = None,
        from_date: timezone.datetime | None = None,
        to_date: timezone.datetime | None = None,
    ) -> QuerySet[AuditEvent]:
        """Search audit events with administrative filters (FR-18, SCR-13)."""
        qs = AuditEvent.objects.select_related("actor", "target_user").all()

        if actor_id is not None:
            qs = qs.filter(actor_id=actor_id)
        if action:
            qs = qs.filter(action=action)
        if request_id is not None:
            qs = qs.filter(request_id=request_id)
        if from_date:
            qs = qs.filter(occurred_at__gte=from_date)
        if to_date:
            qs = qs.filter(occurred_at__lte=to_date)

        return qs.order_by("-occurred_at", "-id")
