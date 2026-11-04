"""Audit log domain model and enumerations (Table 5.5, 5.6, 5.7, FR-17, NFR-05)."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditAction(models.TextChoices):
    """Enumeration of all system audit actions (Table 5.5)."""

    REQUEST_SUBMITTED = "REQUEST_SUBMITTED", "Request Submitted"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED", "Clarification Requested"
    CLARIFICATION_PROVIDED = "CLARIFICATION_PROVIDED", "Clarification Provided"
    REQUEST_APPROVED = "REQUEST_APPROVED", "Request Approved"
    REQUEST_REJECTED = "REQUEST_REJECTED", "Request Rejected"
    WORK_ASSIGNED = "WORK_ASSIGNED", "Work Assigned"
    WORK_REASSIGNED = "WORK_REASSIGNED", "Work Reassigned"
    WORK_STARTED = "WORK_STARTED", "Work Started"
    WORK_COMPLETED = "WORK_COMPLETED", "Work Completed"
    REQUEST_VERIFIED_CLOSED = "REQUEST_VERIFIED_CLOSED", "Request Verified Closed"
    REQUEST_REOPENED = "REQUEST_REOPENED", "Request Reopened"
    USER_CREATED = "USER_CREATED", "User Created"
    USER_IMPORTED = "USER_IMPORTED", "User Imported"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED", "User Role Changed"
    USER_DEACTIVATED = "USER_DEACTIVATED", "User Deactivated"
    USER_REACTIVATED = "USER_REACTIVATED", "User Reactivated"
    PASSWORD_RESET = "PASSWORD_RESET", "Password Reset"
    PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password Changed"
    LOGIN_FAILED = "LOGIN_FAILED", "Login Failed"


class AuditEvent(models.Model):
    """Append-only audit record capturing state transitions and security events (Table 5.7)."""

    id = models.BigAutoField(primary_key=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    action = models.CharField(max_length=30, choices=AuditAction.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="actor_audit_events",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="target_audit_events",
    )
    request_id = models.BigIntegerField(null=True, blank=True)
    work_order_id = models.BigIntegerField(null=True, blank=True)
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ("-occurred_at", "-id")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(action__in=AuditAction.values),
                name="check_audit_action",
            ),
        )
        indexes = (
            models.Index(fields=["request_id", "occurred_at"], name="idx_audit_request_occurred"),
            models.Index(fields=["actor", "occurred_at"], name="idx_audit_actor_occurred"),
            models.Index(fields=["action", "occurred_at"], name="idx_audit_action_occurred"),
        )

    def __str__(self):
        actor_label = self.actor.email if self.actor else "System"
        return f"[{self.occurred_at:%Y-%m-%d %H:%M:%S}] {self.action} by {actor_label}"
