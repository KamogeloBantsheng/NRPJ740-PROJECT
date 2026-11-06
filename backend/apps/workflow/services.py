import uuid
from datetime import timedelta
from typing import Any

from config.exceptions import ConflictException, ForbiddenException, NotFoundException, ValidationException
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, DateTimeField, DurationField, ExpressionWrapper, F, Q, Value
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.audit.models import AuditAction
from apps.audit.services import AuditService
from apps.locations.models import FaultCategory, Location, LocationKind, Residence
from apps.workflow.models import (
    EndReason,
    MaintenanceRequest,
    Priority,
    RequestStatus,
    TransitionRule,
    WorkOrder,
)


class TransitionService:
    """Orchestrates all request state transitions under row locks (System Specification Section 5, Section 5.1).

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
        """T1: Initial fault report submission by a resident or residence warden.

        Enforces resident/warden role, residence boundary (INV-4), active master data,
        trimmed description length (10 to 2000 chars), idempotency via client_token,
        and logs REQUEST_SUBMITTED audit event.
        """
        # 1. Actor check
        if resident.role not in (Role.RESIDENT, Role.WARDEN):
            raise ForbiddenException("Only residents and residence wardens can submit maintenance requests.")
        if not resident.is_active:
            raise ForbiddenException("Your account is deactivated.")

        # 2. Scope & location validation (INV-4: Must be in the user's residence)
        if not resident.residence_id or location.residence_id != resident.residence_id:
            raise ValidationException(
                "Location must be within your assigned residence.",
                fields={"location": ["Selected location is outside your assigned residence."]},
            )

        # 2b. Student room scoping guard:
        # Residents can only submit for their assigned room or common areas.
        # Wardens can choose from all rooms and common areas in their residence.
        if resident.role == Role.RESIDENT:
            is_assigned_room = (
                resident.assigned_location_id is not None
                and location.id == resident.assigned_location_id
            )
            is_common_area = (location.kind == LocationKind.COMMON_AREA)
            if not (is_assigned_room or is_common_area):
                raise ValidationException(
                    "Residents can only submit requests for their assigned room or common areas.",
                    fields={
                        "location": ["Residents can only submit requests for their assigned room or common areas."]
                    },
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
        try:
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
        except IntegrityError:
            # Two simultaneous submits with one token: the unique constraint let one through (AC-05.3)
            existing = MaintenanceRequest.objects.filter(resident=resident, client_token=client_token).first()
            if existing is None:
                raise
            return existing, False

        return req, True

    @staticmethod
    def _authorize(*, req: MaintenanceRequest, action: str, actor: User) -> None:
        """Decide whether the actor's role may perform the action at all (NFR-01).

        This runs before any state check: a role that may never do something gets 403
        whatever state the request happens to be in, not a 409 that reveals the state.
        """
        rule = TransitionRule.objects.filter(action=action).first()
        if rule is None:
            return  # Unknown actions fall through to the 409 refusal below

        if rule.actor_role == Role.RESIDENT:
            # "Owner" in Table 5.1: the person who reported the fault, which may be a Warden
            # reporting on behalf of a Resident.
            if req.resident_id != actor.id:
                raise ForbiddenException("Only the person who submitted the request may perform this action.")
            return

        if rule.actor_role != actor.role:
            raise ForbiddenException(
                f"Role '{actor.role}' is not permitted to perform '{action}'. Required: '{rule.actor_role}'."
            )

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

        Verifies the actor may perform the action (403), checks expected_status (409 on mismatch),
        matches against the TransitionRule table, updates state and timestamps, and creates the
        append-only audit event.
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

            # 2. Role and ownership (403), before anything about state is revealed
            cls._authorize(req=req, action=action, actor=actor)

            # 3. Concurrency check (409 if status differs from expected)
            if expected_status and req.status != expected_status:
                raise ConflictException(
                    f"Request status has changed from '{expected_status}' to '{req.status}'.",
                    current_status=req.status,
                )

            # 4. Match against TransitionRule
            rule = TransitionRule.objects.filter(
                action=action,
                from_status=req.status,
            ).first()
            if not rule:
                raise ConflictException(
                    f"Action '{action}' is not permitted from status '{req.status}'.",
                    current_status=req.status,
                )

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

            elif action == "VERIFY_CLOSE":
                active_wo = (
                    WorkOrder.objects.select_for_update()
                    .filter(request=req, ended_at__isnull=True)
                    .first()
                )
                if active_wo:
                    active_wo.ended_at = timezone.now()
                    active_wo.end_reason = EndReason.COMPLETED
                    active_wo.save()
                    work_order_id = active_wo.id
                    audit_details.update({
                        "work_order_id": active_wo.id,
                        "technician_id": active_wo.technician_id,
                        "technician_name": active_wo.technician.full_name,
                    })
                if trimmed_note:
                    audit_details["closure_note"] = trimmed_note

            elif action == "REOPEN":
                active_wo = WorkOrder.objects.filter(request=req, ended_at__isnull=True).first()
                if active_wo:
                    work_order_id = active_wo.id
                    audit_details.update({
                        "work_order_id": active_wo.id,
                        "technician_id": active_wo.technician_id,
                        "technician_name": active_wo.technician.full_name,
                    })
                audit_details["reopen_reason"] = trimmed_note

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


class ReportingService:
    """Operational dashboard metrics and role-scoped reporting service (FR-16, BR-04, NFR-06, SCR-10)."""

    @classmethod
    def get_dashboard_metrics(
        cls,
        *,
        user: User,
        residence_id: int | None = None,
    ) -> dict:
        """Calculate operational aggregates scoped by user role.

        - Warden: strictly scoped to own residence (INV-4, BR-04, TC-36).
        - Supervisor: all residences by default, or filtered by residence_id (TC-37).
        - Every other role: forbidden (HTTP 403).
        - Strictly read-only, excludes resident personal identity.
        """
        if user.role not in (Role.WARDEN, Role.SUPERVISOR):
            raise ForbiddenException("You do not have permission to view the operational dashboard.")

        # Determine residence scoping
        scoped_residence: Residence | None = None
        if user.role == Role.WARDEN:
            # Warden strictly scoped to own residence (BR-04, TC-36)
            scoped_residence = user.residence
        elif residence_id:
            scoped_residence = Residence.objects.filter(id=residence_id).first()

        # Build base queryset
        qs = MaintenanceRequest.objects.all()
        if scoped_residence:
            qs = qs.filter(location__residence_id=scoped_residence.id)

        # 1. Status distribution
        status_map = {st: 0 for st in RequestStatus.values}
        for row in qs.values("status").annotate(count=Count("id")):
            status_map[row["status"]] = row["count"]

        # 2. Priority distribution
        priority_map = {pr: 0 for pr in Priority.values}
        priority_map["UNASSIGNED"] = 0
        for row in qs.values("priority").annotate(count=Count("id")):
            p_val = row["priority"]
            if p_val and p_val in priority_map:
                priority_map[p_val] = row["count"]
            else:
                priority_map["UNASSIGNED"] += row["count"]

        # 3. Category distribution
        all_categories = FaultCategory.objects.filter(is_active=True).order_by("name")
        cat_counts_raw = {
            row["category_id"]: row["count"]
            for row in qs.values("category_id").annotate(count=Count("id"))
        }
        category_list = [
            {
                "id": cat.id,
                "name": cat.name,
                "count": cat_counts_raw.get(cat.id, 0),
            }
            for cat in all_categories
        ]

        # 4. Open vs Closed counts
        terminal_statuses = [RequestStatus.VERIFIED_CLOSED, RequestStatus.REJECTED]
        open_qs = qs.exclude(status__in=terminal_statuses)
        closed_qs = qs.filter(status__in=terminal_statuses)

        total_requests = qs.count()
        open_requests_count = open_qs.count()
        closed_requests_count = closed_qs.count()

        # 5. Open Request Aging Breakdown
        now = timezone.now()
        day1 = now - timedelta(hours=24)
        day3 = now - timedelta(days=3)
        day7 = now - timedelta(days=7)

        open_age = ExpressionWrapper(Value(now, output_field=DateTimeField()) - F("created_at"), DurationField())
        open_stats = open_qs.aggregate(
            under_24h=Count("id", filter=Q(created_at__gte=day1)),
            one_to_three=Count("id", filter=Q(created_at__lt=day1, created_at__gte=day3)),
            three_to_seven=Count("id", filter=Q(created_at__lt=day3, created_at__gte=day7)),
            over_seven=Count("id", filter=Q(created_at__lt=day7)),
            average_age=Avg(open_age),
        )
        aging_brackets = {
            "under_24h": open_stats["under_24h"],
            "1_to_3_days": open_stats["one_to_three"],
            "3_to_7_days": open_stats["three_to_seven"],
            "over_7_days": open_stats["over_seven"],
        }
        average_age = open_stats["average_age"]
        avg_open_age_hours = round(average_age.total_seconds() / 3600, 1) if average_age else 0.0

        # 6. Mean Time to Closure (MTTC)
        closure_time = ExpressionWrapper(F("closed_at") - F("created_at"), DurationField())
        mean_closure = closed_qs.filter(closed_at__isnull=False).aggregate(mean=Avg(closure_time))["mean"]
        mttc_hours = round(mean_closure.total_seconds() / 3600, 1) if mean_closure else 0.0
        mttc_days = round(mttc_hours / 24, 1)

        # 7. Active work orders in scope
        active_work_orders_count = WorkOrder.objects.filter(
            request__in=open_qs,
            ended_at__isnull=True,
        ).count()

        # Available residences for Supervisor filter dropdown
        residence_options = []
        if user.role == Role.SUPERVISOR:
            residence_options = list(
                Residence.objects.filter(is_active=True).values("id", "name")
            )

        return {
            "scope": {
                "role": user.role,
                "is_scoped_to_residence": scoped_residence is not None,
                "residence_id": scoped_residence.id if scoped_residence else None,
                "residence_name": scoped_residence.name if scoped_residence else "All Residences",
                "available_residences": residence_options,
            },
            "summary": {
                "total_requests": total_requests,
                "open_requests": open_requests_count,
                "closed_requests": closed_requests_count,
                "active_work_orders": active_work_orders_count,
                "average_open_age_hours": avg_open_age_hours,
                "mean_time_to_closure_hours": mttc_hours,
                "mean_time_to_closure_days": mttc_days,
            },
            "status_counts": status_map,
            "priority_counts": priority_map,
            "category_counts": category_list,
            "aging_distribution": aging_brackets,
        }

