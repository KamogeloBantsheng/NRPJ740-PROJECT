"""Workflow domain models: MaintenanceRequest and TransitionRule (Table 5.1, 5.5, 5.6, 5.7)."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Value
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual


class RequestStatus(models.TextChoices):
    """Enumeration of maintenance request states (Table 5.5)."""

    SUBMITTED = "SUBMITTED", "Submitted"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION", "Needs Clarification"
    REJECTED = "REJECTED", "Rejected"
    APPROVED = "APPROVED", "Approved"
    ASSIGNED = "ASSIGNED", "Assigned"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    WORK_COMPLETED = "WORK_COMPLETED", "Work Completed"
    REOPENED = "REOPENED", "Reopened"
    VERIFIED_CLOSED = "VERIFIED_CLOSED", "Verified Closed"


class Priority(models.TextChoices):
    """Enumeration of maintenance priorities (Table 5.5)."""

    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class MaintenanceRequest(models.Model):
    """Fault report domain model (Table 5.7).

    Request status is modified solely via TransitionService.execute(), never directly
    or through model methods (AGENT_BRIEF section 5, Section 5.4).
    """

    id = models.BigAutoField(primary_key=True)
    resident = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name="maintenance_requests",
        db_column="resident_id",
    )
    location = models.ForeignKey(
        "locations.Location",
        on_delete=models.RESTRICT,
        related_name="maintenance_requests",
        db_column="location_id",
    )
    category = models.ForeignKey(
        "locations.FaultCategory",
        on_delete=models.RESTRICT,
        related_name="maintenance_requests",
        db_column="category_id",
    )
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.SUBMITTED,
    )
    priority = models.CharField(
        max_length=8,
        choices=Priority.choices,
        null=True,
        blank=True,
    )
    client_token = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "maintenance_requests"
        ordering = ("-created_at",)
        constraints = (
            models.UniqueConstraint(
                fields=["resident", "client_token"],
                name="unique_resident_client_token",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=RequestStatus.values),
                name="check_request_status",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__in=Priority.values) | models.Q(priority__isnull=True),
                name="check_request_priority",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=[
                            RequestStatus.APPROVED,
                            RequestStatus.ASSIGNED,
                            RequestStatus.IN_PROGRESS,
                            RequestStatus.WORK_COMPLETED,
                            RequestStatus.REOPENED,
                            RequestStatus.VERIFIED_CLOSED,
                        ],
                        priority__isnull=False,
                    )
                    | ~models.Q(
                        status__in=[
                            RequestStatus.APPROVED,
                            RequestStatus.ASSIGNED,
                            RequestStatus.IN_PROGRESS,
                            RequestStatus.WORK_COMPLETED,
                            RequestStatus.REOPENED,
                            RequestStatus.VERIFIED_CLOSED,
                        ]
                    )
                ),
                name="check_priority_not_null_for_approved_and_later",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=[RequestStatus.REJECTED, RequestStatus.VERIFIED_CLOSED],
                        closed_at__isnull=False,
                    )
                    | (
                        models.Q(~models.Q(status__in=[RequestStatus.REJECTED, RequestStatus.VERIFIED_CLOSED]))
                        & models.Q(closed_at__isnull=True)
                    )
                ),
                name="check_closed_at_set_for_terminal_status_only",
            ),
            models.CheckConstraint(
                condition=(
                    GreaterThanOrEqual(Length(Trim(F("description"))), Value(10))
                    & LessThanOrEqual(Length(Trim(F("description"))), Value(2000))
                ),
                name="check_description_length",
            ),
        )
        indexes = (
            models.Index(fields=["status", "created_at"], name="idx_req_status_created"),
            models.Index(fields=["resident", "-created_at"], name="idx_req_resident_created_desc"),
            models.Index(fields=["location"], name="idx_req_location"),
            models.Index(fields=["category"], name="idx_req_category"),
        )

    @property
    def tracking_number(self) -> str:
        """Formatted human-readable tracking number (e.g. MR-000123) from primary key."""
        return f"MR-{self.id:06d}"

    def __str__(self) -> str:
        return f"{self.tracking_number} [{self.status}] {self.description[:30]}"


class TransitionRule(models.Model):
    """Database representation of legal lifecycle transitions (Table 5.1)."""

    id = models.BigAutoField(primary_key=True)
    transition_id = models.CharField(max_length=8, unique=True)
    action = models.CharField(max_length=30)
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20, choices=RequestStatus.choices)
    actor_role = models.CharField(max_length=20)
    audit_action = models.CharField(max_length=30)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "transition_rules"
        ordering = ("transition_id",)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(from_status__in=RequestStatus.values) | models.Q(from_status__isnull=True),
                name="check_transition_from_status",
            ),
            models.CheckConstraint(
                condition=models.Q(to_status__in=RequestStatus.values),
                name="check_transition_to_status",
            ),
        )

    def __str__(self) -> str:
        return f"{self.transition_id}: {self.action} ({self.from_status} -> {self.to_status})"
