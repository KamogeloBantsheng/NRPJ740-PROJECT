from datetime import datetime, time, timedelta
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

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
        from_date: Any = None,
        to_date: Any = None,
        search: str | None = None,
    ) -> QuerySet[AuditEvent]:
        """Search audit events with administrative filters (FR-18, SCR-13)."""
        qs = AuditEvent.objects.select_related("actor", "target_user").all()

        if actor_id is not None:
            qs = qs.filter(actor_id=actor_id)
        if action and action.strip():
            qs = qs.filter(action=action.strip())
        if request_id is not None:
            qs = qs.filter(request_id=request_id)

        # Handle from_date
        if from_date:
            if isinstance(from_date, str) and from_date.strip():
                dt = parse_datetime(from_date)
                if not dt:
                    d = parse_date(from_date)
                    if d:
                        dt = timezone.make_aware(datetime.combine(d, time.min))
                if dt:
                    qs = qs.filter(occurred_at__gte=dt)
            elif hasattr(from_date, "tzinfo"):
                qs = qs.filter(occurred_at__gte=from_date)

        # Handle to_date
        if to_date:
            if isinstance(to_date, str) and to_date.strip():
                dt = parse_datetime(to_date)
                if not dt:
                    d = parse_date(to_date)
                    if d:
                        dt = timezone.make_aware(datetime.combine(d, time.max))
                if dt:
                    qs = qs.filter(occurred_at__lte=dt)
            elif hasattr(to_date, "tzinfo"):
                qs = qs.filter(occurred_at__lte=to_date)

        # Free text search across actor, target_user, notes, and tracking ID
        if search and search.strip():
            term = search.strip()
            # If search matches tracking ID "MR-000123"
            if term.upper().startswith("MR-") and term[3:].isdigit():
                qs = qs.filter(request_id=int(term[3:]))
            elif term.isdigit():
                qs = qs.filter(Q(request_id=int(term)) | Q(actor_id=int(term)))
            else:
                qs = qs.filter(
                    Q(actor__email__icontains=term)
                    | Q(actor__full_name__icontains=term)
                    | Q(target_user__email__icontains=term)
                    | Q(target_user__full_name__icontains=term)
                    | Q(note__icontains=term)
                )

        return qs.order_by("-occurred_at", "-id")

