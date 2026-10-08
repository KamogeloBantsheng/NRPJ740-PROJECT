"""Canonical Table 5.1 lifecycle transition rules and sync utility."""

from apps.accounts.models import Role
from apps.audit.models import AuditAction
from apps.workflow.models import RequestStatus, TransitionRule

TABLE_5_1_RULES = [
    {
        "transition_id": "T1",
        "action": "SUBMIT",
        "from_status": None,
        "to_status": RequestStatus.SUBMITTED,
        "actor_role": Role.RESIDENT,
        "audit_action": AuditAction.REQUEST_SUBMITTED,
        "description": "Resident submits fault report for room or common area in own residence.",
    },
    {
        "transition_id": "T2",
        "action": "REQUEST_CLARIFICATION",
        "from_status": RequestStatus.SUBMITTED,
        "to_status": RequestStatus.NEEDS_CLARIFICATION,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.CLARIFICATION_REQUESTED,
        "description": "Supervisor requests additional details from resident.",
    },
    {
        "transition_id": "T3",
        "action": "PROVIDE_CLARIFICATION",
        "from_status": RequestStatus.NEEDS_CLARIFICATION,
        "to_status": RequestStatus.SUBMITTED,
        "actor_role": Role.RESIDENT,
        "audit_action": AuditAction.CLARIFICATION_PROVIDED,
        "description": "Resident provides requested clarification response.",
    },
    {
        "transition_id": "T4",
        "action": "APPROVE",
        "from_status": RequestStatus.SUBMITTED,
        "to_status": RequestStatus.APPROVED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.REQUEST_APPROVED,
        "description": "Supervisor approves request and assigns priority.",
    },
    {
        "transition_id": "T5_SUB",
        "action": "REJECT",
        "from_status": RequestStatus.SUBMITTED,
        "to_status": RequestStatus.REJECTED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.REQUEST_REJECTED,
        "description": "Supervisor rejects submitted request with mandatory reason.",
    },
    {
        "transition_id": "T5_APP",
        "action": "REJECT",
        "from_status": RequestStatus.APPROVED,
        "to_status": RequestStatus.REJECTED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.REQUEST_REJECTED,
        "description": "Supervisor rejects approved request with mandatory reason.",
    },
    {
        "transition_id": "T6",
        "action": "ASSIGN",
        "from_status": RequestStatus.APPROVED,
        "to_status": RequestStatus.ASSIGNED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.WORK_ASSIGNED,
        "description": "Supervisor assigns active technician and creates work order.",
    },
    {
        "transition_id": "T7_ASG",
        "action": "REASSIGN",
        "from_status": RequestStatus.ASSIGNED,
        "to_status": RequestStatus.ASSIGNED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.WORK_REASSIGNED,
        "description": "Supervisor reassigns assigned request to different technician.",
    },
    {
        "transition_id": "T7_PROG",
        "action": "REASSIGN",
        "from_status": RequestStatus.IN_PROGRESS,
        "to_status": RequestStatus.ASSIGNED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.WORK_REASSIGNED,
        "description": "Supervisor reassigns in-progress request to different technician.",
    },
    {
        "transition_id": "T7_REOP",
        "action": "REASSIGN",
        "from_status": RequestStatus.REOPENED,
        "to_status": RequestStatus.ASSIGNED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.WORK_REASSIGNED,
        "description": "Supervisor reassigns reopened request to different technician.",
    },
    {
        "transition_id": "T8_ASG",
        "action": "START_WORK",
        "from_status": RequestStatus.ASSIGNED,
        "to_status": RequestStatus.IN_PROGRESS,
        "actor_role": Role.TECHNICIAN,
        "audit_action": AuditAction.WORK_STARTED,
        "description": "Assigned technician commences physical repair work.",
    },
    {
        "transition_id": "T8_REOP",
        "action": "START_WORK",
        "from_status": RequestStatus.REOPENED,
        "to_status": RequestStatus.IN_PROGRESS,
        "actor_role": Role.TECHNICIAN,
        "audit_action": AuditAction.WORK_STARTED,
        "description": "Assigned technician recommences work on reopened request.",
    },
    {
        "transition_id": "T9",
        "action": "COMPLETE_WORK",
        "from_status": RequestStatus.IN_PROGRESS,
        "to_status": RequestStatus.WORK_COMPLETED,
        "actor_role": Role.TECHNICIAN,
        "audit_action": AuditAction.WORK_COMPLETED,
        "description": "Assigned technician records completion with detailed notes.",
    },
    {
        "transition_id": "T10",
        "action": "VERIFY_CLOSE",
        "from_status": RequestStatus.WORK_COMPLETED,
        "to_status": RequestStatus.VERIFIED_CLOSED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.REQUEST_VERIFIED_CLOSED,
        "description": "Supervisor inspects and verifies completed work, closing request.",
    },
    {
        "transition_id": "T11",
        "action": "REOPEN",
        "from_status": RequestStatus.WORK_COMPLETED,
        "to_status": RequestStatus.REOPENED,
        "actor_role": Role.SUPERVISOR,
        "audit_action": AuditAction.REQUEST_REOPENED,
        "description": "Supervisor reopens unsatisfactory work with feedback notes.",
    },
]


def sync_transition_rules() -> int:
    """Idempotently sync canonical Table 5.1 rules into database transition_rules table."""
    count = 0
    for rule_data in TABLE_5_1_RULES:
        TransitionRule.objects.update_or_create(
            transition_id=rule_data["transition_id"],
            defaults={
                "action": rule_data["action"],
                "from_status": rule_data["from_status"],
                "to_status": rule_data["to_status"],
                "actor_role": rule_data["actor_role"],
                "audit_action": rule_data["audit_action"],
                "description": rule_data["description"],
            },
        )
        count += 1
    return count
