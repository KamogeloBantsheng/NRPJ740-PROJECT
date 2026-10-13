"""TransitionService implementing Table 5.1 lifecycle transitions, row-locking, and audit logging."""

import uuid
from typing import Any

from config.exceptions import ConflictException, ForbiddenException, NotFoundException, ValidationException
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.audit.models import AuditAction
from apps.audit.services import AuditService
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import (
    EndReason,
    MaintenanceRequest,
    Priority,
    RequestStatus,
    TransitionRule,
    WorkOrder,
)


class TransitionService:
    """Orchestrates all request state transitions under row locks (AGENT_BRIEF section 5, Section 5.1).

    Enforces Table 5.1 legal transitions, concurrency guards via expected_status (409),
    role-based transition authorization, and writes append-only audit records in the same transaction.
    """

    @classmethod
    def submit_request(
        cls,
        *,
        resident: User,
        location: Location,
        category: FaultCategory,
        description: str,
        client_token: uuid.UUID | None = None,
    ) -> tuple[MaintenanceRequest, bool]:
        """T1: Initial fault report submission by a resident.

        Enforces resident role, residence boundary (INV-4), active master data,
        trimmed description length (10 to 2000 chars), idempotency via client_token,
        and logs REQUEST_SUBMITTED audit event.
        """
        # 1. Actor check
        if resident.role != Role.RESIDENT:
            raise ForbiddenException("Only residents can submit maintenance requests.")
        if not resident.is_active:
            raise ForbiddenException("Your account is deactivated.")

        # 2. Scope & location validation (INV-4: Must be in the Resident's residence)
        if not resident.residence_id or location.residence_id != resident.residence_id:
            raise ValidationException(
                "Location must be within your assigned residence.",
                fields={"location": ["Selected location is outside your assigned residence."]},
            )

        if not location.is_active:
            raise ValidationException(
                "Selected location is inactive.",
                fields={"location": ["Selected location is inactive."]},
            )

        if not category.is_active:
            raise ValidationException(
                "Selected fault category is inactive.",
                fields={"category": ["Selected fault category is inactive."]},
            )

        # 3. Description validation (10 to 2000 characters trimmed)
        trimmed_desc = description.strip()
        if len(trimmed_desc) < 10 or len(trimmed_desc) > 2000:
            raise ValidationException(
                "Description must be between 10 and 2,000 characters.",
                fields={"description": ["Description must be between 10 and 2,000 characters."]},
            )

        # 4. Idempotency check
        if client_token:
            existing = MaintenanceRequest.objects.filter(
                resident=resident,
                client_token=client_token,
            ).first()
            if existing:
                return existing, False
        else:
            client_token = uuid.uuid4()

        # 5. Atomic persistence and audit recording
        with transaction.atomic():
            req = MaintenanceRequest.objects.create(
                resident=resident,
                location=location,
                category=category,
                description=trimmed_desc,
                status=RequestStatus.SUBMITTED,
                priority=None,
                client_token=client_token,
                closed_at=None,
            )

            AuditService.record(
                action=AuditAction.REQUEST_SUBMITTED,
                actor=resident,
                request_id=req.id,
                from_status=None,
                to_status=RequestStatus.SUBMITTED,
                details={
                    "tracking_number": req.tracking_number,
                    "location_id": location.id,
                    "location_label": location.label,
                    "location_kind": location.kind,
                    "category_id": category.id,
                    "category_name": category.name,
                },
            )

            return req, True

    @classmethod
    def execute(
        cls,
        *,
        request_id: int,
        action: str,
        actor: User,
        expected_status: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> MaintenanceRequest:
        """Execute a state transition under a row lock (SELECT FOR UPDATE).

        Checks expected_status (409 on mismatch), matches against TransitionRule table,
        verifies actor role, updates state and timestamps, and creates append-only audit event.
        """
        payload = payload or {}

        with transaction.atomic():
            # 1. Lock the request row first
            req = (
                MaintenanceRequest.objects.select_for_update()
                .filter(id=request_id)
                .first()
            )
            if not req:
                raise NotFoundException(f"Maintenance request {request_id} not found.")

            # 2. Concurrency check (409 if status differs from expected)
            if expected_status and req.status != expected_status:
                raise ConflictException(
                    f"Request status has changed from '{expected_status}' to '{req.status}'.",
                    current_status=req.status,
                )

            # 3. Match against TransitionRule
            rule = TransitionRule.objects.filter(
                action=action,
                from_status=req.status,
            ).first()
            if not rule:
                raise ConflictException(
                    f"Action '{action}' is not permitted from status '{req.status}'.",
                    current_status=req.status,
                )

            # 4. Check actor authorization
            if rule.actor_role != actor.role:
                raise ForbiddenException(
                    f"Role '{actor.role}' is not permitted to perform '{action}'. Required: '{rule.actor_role}'."
                )

            # Additional owner check for Resident actions (e.g. PROVIDE_CLARIFICATION)
            if rule.actor_role == Role.RESIDENT and req.resident_id != actor.id:
                raise ForbiddenException("Only the resident who submitted the request may perform this action.")

            # Additional assigned technician check for Technician actions (START_WORK, COMPLETE_WORK)
            if rule.actor_role == Role.TECHNICIAN:
                active_wo = WorkOrder.objects.filter(request=req, ended_at__isnull=True).first()
                if not active_wo or active_wo.technician_id != actor.id:
                    raise ForbiddenException("Only the technician assigned to this request can perform this action.")

            # Residence boundary check for Supervisor
            if actor.role == Role.SUPERVISOR and actor.residence_id:
                if req.location.residence_id != actor.residence_id:
                    raise ForbiddenException("You cannot transition requests outside your assigned residence.")

            old_status = req.status
            new_status = rule.to_status

            # Guard validation per action (Table 5.1 & BR-02, BR-08)
            note = payload.get("note", "")
            trimmed_note = note.strip() if isinstance(note, str) else ""

            if action in ("REQUEST_CLARIFICATION", "PROVIDE_CLARIFICATION", "REJECT", "REASSIGN", "REOPEN"):
                if len(trimmed_note) < 10:
                    raise ValidationException(
                        f"Action '{action}' requires a note or reason of at least 10 characters.",
                        fields={"note": ["Note must be at least 10 characters long."]},
                    )
            elif action == "COMPLETE_WORK":
                if len(trimmed_note) < 20:
                    raise ValidationException(
                        "Work completion requires notes of at least 20 characters.",
                        fields={"note": ["Work completion notes must be at least 20 characters long."]},
                    )

            if action == "APPROVE":
                priority = payload.get("priority")
                if not priority or priority not in Priority.values:
                    raise ValidationException(
                        "A valid priority (LOW, MEDIUM, HIGH, CRITICAL) is required to approve a request.",
                        fields={"priority": ["Priority is required for approval."]},
                    )
                req.priority = priority

            # 5. Work order handling under NFR-04 lock ordering (Request row locked first, Technician row locked second)
            work_order_id = None
            audit_details = payload.get("details", {}).copy()

            if action == "ASSIGN":
                tech_id = payload.get("technician_id")
                if not tech_id:
                    raise ValidationException(
                        "Technician ID is required for assignment.",
                        fields={"technician_id": ["Please select a technician."]},
                    )

                tech = (
                    User.objects.select_for_update()
                    .filter(id=tech_id, role=Role.TECHNICIAN)
                    .first()
                )
                if not tech:
                    raise ValidationException(
                        "Selected technician does not exist.",
                        fields={"technician_id": ["Technician not found."]},
                    )
                if not tech.is_active:
                    raise ValidationException(
                        "Cannot assign request to a deactivated technician.",
                        fields={"technician_id": ["Technician account is deactivated."]},
                    )

                existing_active = WorkOrder.objects.filter(request=req, ended_at__isnull=True).first()
                if existing_active:
                    raise ConflictException("Request already has an active work order.")

                wo = WorkOrder.objects.create(
                    request=req,
                    technician=tech,
                    assigned_by=actor,
                )
                work_order_id = wo.id
                audit_details.update({
                    "technician_id": tech.id,
                    "technician_name": tech.full_name,
                })

            elif action == "REASSIGN":
                tech_id = payload.get("technician_id")
                if not tech_id:
                    raise ValidationException(
                        "Technician ID is required for reassignment.",
                        fields={"technician_id": ["Please select a technician to reassign to."]},
                    )

                new_tech = (
                    User.objects.select_for_update()
                    .filter(id=tech_id, role=Role.TECHNICIAN)
                    .first()
                )
                if not new_tech:
                    raise ValidationException(
                        "Selected technician does not exist.",
                        fields={"technician_id": ["Technician not found."]},
                    )
                if not new_tech.is_active:
                    raise ValidationException(
                        "Cannot reassign request to a deactivated technician.",
                        fields={"technician_id": ["Technician account is deactivated."]},
                    )

                current_wo = (
                    WorkOrder.objects.select_for_update()
                    .filter(request=req, ended_at__isnull=True)
                    .first()
                )
                if not current_wo:
                    raise ConflictException("No active work order found to reassign.")

                if current_wo.technician_id == new_tech.id:
                    raise ValidationException(
                        "Must reassign to a different active technician.",
                        fields={"technician_id": ["Selected technician is already assigned to this request."]},
                    )

                current_wo.ended_at = timezone.now()
                current_wo.end_reason = EndReason.REASSIGNED
                current_wo.save()

                new_wo = WorkOrder.objects.create(
                    request=req,
                    technician=new_tech,
                    assigned_by=actor,
                )
                work_order_id = new_wo.id
                audit_details.update({
                    "previous_technician_id": current_wo.technician_id,
                    "previous_technician_name": current_wo.technician.full_name,
                    "new_technician_id": new_tech.id,
                    "new_technician_name": new_tech.full_name,
                    "reason": trimmed_note,
                })

            elif action in ("START_WORK", "COMPLETE_WORK"):
                active_wo = WorkOrder.objects.filter(request=req, ended_at__isnull=True).first()
                if not active_wo or active_wo.technician_id != actor.id:
                    raise ForbiddenException("Only the technician assigned to this request can perform this action.")
                work_order_id = active_wo.id
                audit_details.update({
                    "work_order_id": active_wo.id,
                    "technician_id": actor.id,
                    "technician_name": actor.full_name,
                })
                if action == "COMPLETE_WORK":
                    audit_details["completion_notes"] = trimmed_note

            # 6. Apply state changes
            req.status = new_status

            # Handle terminal closure timestamp
            if new_status in (RequestStatus.REJECTED, RequestStatus.VERIFIED_CLOSED):
                req.closed_at = timezone.now()
            else:
                req.closed_at = None

            req.save()

            # 7. Record append-only audit event
            AuditService.record(
                action=rule.audit_action,
                actor=actor,
                request_id=req.id,
                work_order_id=work_order_id,
                from_status=old_status,
                to_status=new_status,
                note=trimmed_note if trimmed_note else None,
                details=audit_details,
            )

            return req
