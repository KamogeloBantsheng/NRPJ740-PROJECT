"""Workflow & Lifecycle State Machine Test Suite (Phase 10: TC-10 to TC-35).

Covers Table 5.1 state machine transitions (T1 to T11), client token idempotency,
validation rules (BR-02, BR-08, INV-4), work order dispatching, and terminal state immutability.
"""

import uuid

import pytest
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import (
    EndReason,
    MaintenanceRequest,
    Priority,
    RequestStatus,
    WorkOrder,
)
from apps.workflow.services import TransitionService
from config.exceptions import ForbiddenException
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestWorkflowLifecycle:
    """Covers TC-10 through TC-35."""

    def test_tc10_request_submission_valid_payload(
        self,
        resident_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-10: Valid fault report payload creates SUBMITTED request and emits audit event (FR-05, SCR-04)."""
        payload = {
            "location_id": location.id,
            "category_id": category.id,
            "description": "The hot water tap in the bathroom is constantly dripping and loose.",
        }
        resp = resident_client.post("/api/requests/", payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()

        assert data["status"] == RequestStatus.SUBMITTED
        assert data["priority"] is None
        assert data["description"] == payload["description"]
        assert data["tracking_number"].startswith("MR-")
        assert data["location"]["id"] == location.id
        assert data["category"]["id"] == category.id

        # Verify audit record
        audit = AuditEvent.objects.filter(
            action=AuditAction.REQUEST_SUBMITTED,
            request_id=data["id"],
        ).first()
        assert audit is not None
        assert audit.actor_id == resident_user.id
        assert audit.to_status == RequestStatus.SUBMITTED

    def test_tc11_duplicate_submission_idempotency(
        self,
        resident_client: APIClient,
        location: Location,
        category: FaultCategory,
    ):
        """TC-11: Duplicate submission with same client_token is idempotent and returns existing request (NFR-04)."""
        client_token = str(uuid.uuid4())
        payload = {
            "location_id": location.id,
            "category_id": category.id,
            "description": "Ceiling light flickering intermittently in corridor.",
            "client_token": client_token,
        }

        # First submission
        resp1 = resident_client.post("/api/requests/", payload, format="json")
        assert resp1.status_code == status.HTTP_201_CREATED
        req_id1 = resp1.json()["id"]

        # Duplicate submission with identical client token
        resp2 = resident_client.post("/api/requests/", payload, format="json")
        assert resp2.status_code == status.HTTP_200_OK
        req_id2 = resp2.json()["id"]

        assert req_id1 == req_id2
        assert MaintenanceRequest.objects.filter(client_token=client_token).count() == 1
        assert AuditEvent.objects.filter(action=AuditAction.REQUEST_SUBMITTED, request_id=req_id1).count() == 1

    def test_tc12_character_limit_and_trimming(
        self,
        resident_client: APIClient,
        location: Location,
        category: FaultCategory,
    ):
        """TC-12: Description < 10 characters or > 2,000 characters rejected with 422; whitespace trimmed."""
        # Too short (< 10 chars)
        short_resp = resident_client.post(
            "/api/requests/",
            {"location_id": location.id, "category_id": category.id, "description": "Broken"},
            format="json",
        )
        assert short_resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Whitespace-only or trimmed < 10 chars
        padded_resp = resident_client.post(
            "/api/requests/",
            {"location_id": location.id, "category_id": category.id, "description": "    Leak    "},
            format="json",
        )
        assert padded_resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Too long (> 2000 chars)
        long_resp = resident_client.post(
            "/api/requests/",
            {"location_id": location.id, "category_id": category.id, "description": "A" * 2001},
            format="json",
        )
        assert long_resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_tc13_inactive_location_or_category_rejected(
        self,
        resident_client: APIClient,
        location: Location,
        other_res_location: Location,
        category: FaultCategory,
    ):
        """TC-13: Inactive location/category or location outside resident's residence rejected with 422 (INV-4)."""
        # Deactivated location
        location.is_active = False
        location.save()
        resp_inactive_loc = resident_client.post(
            "/api/requests/",
            {"location_id": location.id, "category_id": category.id, "description": "Valid description for repair."},
            format="json",
        )
        assert resp_inactive_loc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        location.is_active = True
        location.save()

        # Deactivated category
        category.is_active = False
        category.save()
        resp_inactive_cat = resident_client.post(
            "/api/requests/",
            {"location_id": location.id, "category_id": category.id, "description": "Valid description for repair."},
            format="json",
        )
        assert resp_inactive_cat.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        category.is_active = True
        category.save()

        # Location outside resident's assigned residence (Luka Jantjie House vs Moroka Hall)
        resp_cross_res = resident_client.post(
            "/api/requests/",
            {
                "location_id": other_res_location.id,
                "category_id": category.id,
                "description": "Valid description for repair.",
            },
            format="json",
        )
        assert resp_cross_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_tc15_clarification_loop(
        self,
        resident_client: APIClient,
        supervisor_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-15: Clarification loop T2/T3 (SUBMITTED -> NEEDS_CLARIFICATION -> SUBMITTED) and state guards."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Strange sound coming from bathroom pipes during evening hours.",
            status=RequestStatus.SUBMITTED,
        )

        # Supervisor requests clarification (T2)
        resp_req_clar = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "REQUEST_CLARIFICATION",
                "expected_status": RequestStatus.SUBMITTED,
                "note": "Please specify whether the sound occurs when the tap is running or idle.",
            },
            format="json",
        )
        assert resp_req_clar.status_code == status.HTTP_200_OK
        assert resp_req_clar.json()["status"] == RequestStatus.NEEDS_CLARIFICATION

        # While in NEEDS_CLARIFICATION, supervisor cannot approve or assign (guarded)
        resp_invalid_approve = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "APPROVE",
                "expected_status": RequestStatus.NEEDS_CLARIFICATION,
                "priority": Priority.MEDIUM,
            },
            format="json",
        )
        assert resp_invalid_approve.status_code == status.HTTP_409_CONFLICT

        # Resident provides clarification (T3)
        resp_prov_clar = resident_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "PROVIDE_CLARIFICATION",
                "expected_status": RequestStatus.NEEDS_CLARIFICATION,
                "note": "The rattling sound happens only when the hot water tap is running.",
            },
            format="json",
        )
        assert resp_prov_clar.status_code == status.HTTP_200_OK
        assert resp_prov_clar.json()["status"] == RequestStatus.SUBMITTED

    def test_tc17_approve_with_priority(
        self,
        supervisor_client: APIClient,
        resident_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-17: T4 Approve moves SUBMITTED -> APPROVED with mandatory priority; non-supervisor forbidden."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Broken window latch causing cold draft into bedroom.",
            status=RequestStatus.SUBMITTED,
        )

        # Non-supervisor (Resident) forbidden
        resp_forbidden = resident_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "APPROVE",
                "expected_status": RequestStatus.SUBMITTED,
                "priority": Priority.HIGH,
            },
            format="json",
        )
        assert resp_forbidden.status_code == status.HTTP_403_FORBIDDEN

        # Approval missing priority rejected with 422
        resp_no_pri = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "APPROVE",
                "expected_status": RequestStatus.SUBMITTED,
            },
            format="json",
        )
        assert resp_no_pri.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Valid approval by Supervisor
        resp_app = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "APPROVE",
                "expected_status": RequestStatus.SUBMITTED,
                "priority": Priority.HIGH,
            },
            format="json",
        )
        assert resp_app.status_code == status.HTTP_200_OK
        data = resp_app.json()
        assert data["status"] == RequestStatus.APPROVED
        assert data["priority"] == Priority.HIGH

    def test_tc18_reject_with_mandatory_reason(
        self,
        supervisor_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-18: T5 Reject moves SUBMITTED -> REJECTED with mandatory note >= 10 chars, sets closed_at."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Resident requests repainting of entire room wall in different color.",
            status=RequestStatus.SUBMITTED,
        )

        # Rejection without note or note < 10 chars rejected
        resp_short_note = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "REJECT",
                "expected_status": RequestStatus.SUBMITTED,
                "note": "Declined",
            },
            format="json",
        )
        assert resp_short_note.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Valid rejection
        resp_rej = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "REJECT",
                "expected_status": RequestStatus.SUBMITTED,
                "note": "Cosmetic modifications outside university maintenance policy.",
            },
            format="json",
        )
        assert resp_rej.status_code == status.HTTP_200_OK
        data = resp_rej.json()
        assert data["status"] == RequestStatus.REJECTED
        assert data["closed_at"] is not None

        req.refresh_from_db()
        assert req.status == RequestStatus.REJECTED
        assert req.closed_at is not None

    def test_tc21_and_tc22_assign_work_order_and_guards(
        self,
        supervisor_client: APIClient,
        resident_user: User,
        technician_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-21 & TC-22: T6 Assign creates WorkOrder; assignment to inactive or non-tech rejected with 422."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Main circuit breaker trips repeatedly when heater is plugged in.",
            status=RequestStatus.APPROVED,
            priority=Priority.CRITICAL,
        )

        # TC-22: Assignment to non-technician (e.g. resident)
        resp_non_tech = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "ASSIGN",
                "expected_status": RequestStatus.APPROVED,
                "technician_id": resident_user.id,
            },
            format="json",
        )
        assert resp_non_tech.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # TC-22: Assignment to deactivated technician
        technician_user.is_active = False
        technician_user.save()
        resp_deact_tech = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "ASSIGN",
                "expected_status": RequestStatus.APPROVED,
                "technician_id": technician_user.id,
            },
            format="json",
        )
        assert resp_deact_tech.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        technician_user.is_active = True
        technician_user.save()

        # TC-21: Valid assignment to active technician
        resp_asg = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "ASSIGN",
                "expected_status": RequestStatus.APPROVED,
                "technician_id": technician_user.id,
            },
            format="json",
        )
        assert resp_asg.status_code == status.HTTP_200_OK
        data = resp_asg.json()
        assert data["status"] == RequestStatus.ASSIGNED
        assert data["active_work_order"]["technician_id"] == technician_user.id

        # Verify WorkOrder row in DB
        wo = WorkOrder.objects.filter(request=req, ended_at__isnull=True).first()
        assert wo is not None
        assert wo.technician_id == technician_user.id

    def test_tc26_and_tc27_reassign_work_order_and_former_tech_guarded(
        self,
        supervisor_client: APIClient,
        technician_client: APIClient,
        resident_user: User,
        supervisor_user: User,
        technician_user: User,
        technician_user_2: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-26 & TC-27: T7 Reassign supersedes current work order; former technician rejected from updating."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Ceiling fan motor hums loudly without rotating blades.",
            status=RequestStatus.ASSIGNED,
            priority=Priority.MEDIUM,
        )
        old_wo = WorkOrder.objects.create(
            request=req,
            technician=technician_user,
            assigned_by=supervisor_user,
        )

        # Supervisor reassigns to technician 2 (T7)
        resp_reassign = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "REASSIGN",
                "expected_status": RequestStatus.ASSIGNED,
                "technician_id": technician_user_2.id,
                "note": "Primary technician dispatched to emergency water pipe burst.",
            },
            format="json",
        )
        assert resp_reassign.status_code == status.HTTP_200_OK
        data = resp_reassign.json()
        assert data["status"] == RequestStatus.ASSIGNED
        assert data["active_work_order"]["technician_id"] == technician_user_2.id

        # Verify old work order ended
        old_wo.refresh_from_db()
        assert old_wo.ended_at is not None
        assert old_wo.end_reason == EndReason.REASSIGNED

        # TC-27: Former technician attempts START_WORK -> rejected via 404 scoping guard on HTTP
        resp_former = technician_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "START_WORK",
                "expected_status": RequestStatus.ASSIGNED,
            },
            format="json",
        )
        assert resp_former.status_code == status.HTTP_404_NOT_FOUND

        # Direct service execution explicitly checks and raises ForbiddenException
        with pytest.raises(ForbiddenException):
            TransitionService.execute(
                request_id=req.id,
                action="START_WORK",
                actor=technician_user,
                expected_status=RequestStatus.ASSIGNED,
            )

    def test_tc29_to_tc33_complete_workflow_lifecycle(
        self,
        supervisor_client: APIClient,
        technician_client: APIClient,
        resident_user: User,
        supervisor_user: User,
        technician_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-29 to TC-33: Complete lifecycle from Assigned -> In Progress -> Completed -> Verified/Reopened."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Shower drain blocked with standing water overflow.",
            status=RequestStatus.ASSIGNED,
            priority=Priority.HIGH,
        )
        wo = WorkOrder.objects.create(
            request=req,
            technician=technician_user,
            assigned_by=supervisor_user,
        )

        # TC-29: T8 Start Work by assigned technician
        resp_start = technician_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "START_WORK",
                "expected_status": RequestStatus.ASSIGNED,
            },
            format="json",
        )
        assert resp_start.status_code == status.HTTP_200_OK
        assert resp_start.json()["status"] == RequestStatus.IN_PROGRESS

        # TC-31: T9 Complete Work rejected if notes < 20 characters
        resp_short_notes = technician_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "COMPLETE_WORK",
                "expected_status": RequestStatus.IN_PROGRESS,
                "note": "Drain unblocked.",
            },
            format="json",
        )
        assert resp_short_notes.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # TC-30: T9 Complete Work with valid notes >= 20 characters
        completion_note = "Cleared drain blockage using snake auger and tested water flow thoroughly."
        resp_complete = technician_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "COMPLETE_WORK",
                "expected_status": RequestStatus.IN_PROGRESS,
                "note": completion_note,
            },
            format="json",
        )
        assert resp_complete.status_code == status.HTTP_200_OK
        assert resp_complete.json()["status"] == RequestStatus.WORK_COMPLETED

        # TC-33: T11 Reopen with feedback notes (unsatisfactory work inspection)
        resp_reopen = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "REOPEN",
                "expected_status": RequestStatus.WORK_COMPLETED,
                "note": "Drain still drains very slowly during basin flush test.",
            },
            format="json",
        )
        assert resp_reopen.status_code == status.HTTP_200_OK
        assert resp_reopen.json()["status"] == RequestStatus.REOPENED

        # Technician recommences work from REOPENED
        resp_re_start = technician_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "START_WORK",
                "expected_status": RequestStatus.REOPENED,
            },
            format="json",
        )
        assert resp_re_start.status_code == status.HTTP_200_OK
        assert resp_re_start.json()["status"] == RequestStatus.IN_PROGRESS

        # Technician completes work again
        resp_re_complete = technician_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "COMPLETE_WORK",
                "expected_status": RequestStatus.IN_PROGRESS,
                "note": "Removed secondary calcium deposit trap and verified full flow rate.",
            },
            format="json",
        )
        assert resp_re_complete.status_code == status.HTTP_200_OK
        assert resp_re_complete.json()["status"] == RequestStatus.WORK_COMPLETED

        # TC-32: T10 Verify Close by supervisor
        resp_close = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "VERIFY_CLOSE",
                "expected_status": RequestStatus.WORK_COMPLETED,
                "note": "Inspected shower drain, verified rapid drainage and clean site.",
            },
            format="json",
        )
        assert resp_close.status_code == status.HTTP_200_OK
        data = resp_close.json()
        assert data["status"] == RequestStatus.VERIFIED_CLOSED
        assert data["closed_at"] is not None

        # Verify work order ended with COMPLETED
        wo.refresh_from_db()
        assert wo.ended_at is not None
        assert wo.end_reason == EndReason.COMPLETED

    def test_tc34_terminal_states_immutable(
        self,
        supervisor_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-34: Requests in terminal states (VERIFIED_CLOSED, REJECTED) cannot be transitioned (409 Conflict)."""
        closed_req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Repaired broken power socket outlet.",
            status=RequestStatus.VERIFIED_CLOSED,
            priority=Priority.MEDIUM,
            closed_at=timezone.now(),
        )

        resp_reopen_closed = supervisor_client.post(
            f"/api/requests/{closed_req.id}/transition/",
            {
                "action": "REOPEN",
                "expected_status": RequestStatus.VERIFIED_CLOSED,
                "note": "Attempting to reopen verified closed request.",
            },
            format="json",
        )
        assert resp_reopen_closed.status_code == status.HTTP_409_CONFLICT

    def test_tc35_exhaustive_illegal_transitions_matrix(
        self,
        supervisor_client: APIClient,
        resident_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-35: Exhaustive testing of illegal transitions and role mismatches per Table 5.1."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Leaking kitchen tap in communal area.",
            status=RequestStatus.SUBMITTED,
        )

        # Illegal action from SUBMITTED: START_WORK is not permitted from SUBMITTED (409 Conflict)
        resp_illegal = supervisor_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "START_WORK",
                "expected_status": RequestStatus.SUBMITTED,
            },
            format="json",
        )
        assert resp_illegal.status_code == status.HTTP_409_CONFLICT

        # Role mismatch: Resident attempting supervisor APPROVE action returns 403 Forbidden
        resp_role_mismatch = resident_client.post(
            f"/api/requests/{req.id}/transition/",
            {
                "action": "APPROVE",
                "expected_status": RequestStatus.SUBMITTED,
                "priority": Priority.HIGH,
            },
            format="json",
        )
        assert resp_role_mismatch.status_code == status.HTTP_403_FORBIDDEN
