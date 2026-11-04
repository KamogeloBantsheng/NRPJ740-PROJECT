"""Database Invariants Verification Test Suite (Phase 10: NT-03).

Executes complex lifecycle pathways (happy path, clarification loops, reassignments,
and reopenings) and systematically verifies that all database invariants (INV-1 to INV-6)
hold true across every operational step.
"""

import random

import pytest
from apps.accounts.models import User
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import MaintenanceRequest, Priority, RequestStatus
from rest_framework import status
from rest_framework.test import APIClient
from tests.conftest import assert_database_invariants


@pytest.mark.django_db
class TestDatabaseInvariants:
    """Covers NT-03: System invariant preservation across complex operational flows."""

    def test_nt03_invariants_hold_across_full_lifecycle_pathways(
        self,
        resident_client: APIClient,
        supervisor_client: APIClient,
        technician_client: APIClient,
        technician_client_2: APIClient,
        resident_user: User,
        supervisor_user: User,
        technician_user: User,
        technician_user_2: User,
        location: Location,
        category: FaultCategory,
    ):
        """NT-03: Invariants INV-1 to INV-6 hold after every step of multi-branch lifecycle workflows."""
        # Baseline check
        assert_database_invariants()

        # Step 1: Submit new request (T1)
        resp_sub = resident_client.post(
            "/api/requests/",
            {
                "location_id": location.id,
                "category_id": category.id,
                "description": "Geyser leaking large amounts of hot water into hallway.",
            },
            format="json",
        )
        assert resp_sub.status_code == status.HTTP_201_CREATED
        req_id = resp_sub.json()["id"]
        assert_database_invariants()

        # Step 2: Request clarification (T2)
        resp_req_clar = supervisor_client.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "REQUEST_CLARIFICATION",
                "expected_status": RequestStatus.SUBMITTED,
                "note": "Is the leak coming from the tank body or the outlet pipe?",
            },
            format="json",
        )
        assert resp_req_clar.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 3: Provide clarification (T3)
        resp_prov_clar = resident_client.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "PROVIDE_CLARIFICATION",
                "expected_status": RequestStatus.NEEDS_CLARIFICATION,
                "note": "It is spraying from the high-pressure valve on the outlet pipe.",
            },
            format="json",
        )
        assert resp_prov_clar.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 4: Approve with Priority (T4)
        resp_app = supervisor_client.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "APPROVE",
                "expected_status": RequestStatus.SUBMITTED,
                "priority": Priority.CRITICAL,
            },
            format="json",
        )
        assert resp_app.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 5: Assign Technician 1 (T6)
        resp_asg = supervisor_client.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "ASSIGN",
                "expected_status": RequestStatus.APPROVED,
                "technician_id": technician_user.id,
            },
            format="json",
        )
        assert resp_asg.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 6: Start Work by Technician 1 (T8)
        resp_start = technician_client.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "START_WORK",
                "expected_status": RequestStatus.ASSIGNED,
            },
            format="json",
        )
        assert resp_start.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 7: Reassign to Technician 2 (T7)
        resp_reassign = supervisor_client.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "REASSIGN",
                "expected_status": RequestStatus.IN_PROGRESS,
                "technician_id": technician_user_2.id,
                "note": "Technician 1 called away to campus substation power failure.",
            },
            format="json",
        )
        assert resp_reassign.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 8: Technician 2 commences work (T8)
        resp_start_2 = technician_client_2.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "START_WORK",
                "expected_status": RequestStatus.ASSIGNED,
            },
            format="json",
        )
        assert resp_start_2.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 9: Technician 2 completes work (T9)
        resp_complete = technician_client_2.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "COMPLETE_WORK",
                "expected_status": RequestStatus.IN_PROGRESS,
                "note": "Replaced faulty high-pressure safety valve and verified zero leakage under pressure.",
            },
            format="json",
        )
        assert resp_complete.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 10: Supervisor reopens for re-inspection (T11)
        resp_reopen = supervisor_client.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "REOPEN",
                "expected_status": RequestStatus.WORK_COMPLETED,
                "note": "Insulation wrap was left off the geyser cylinder body.",
            },
            format="json",
        )
        assert resp_reopen.status_code == status.HTTP_200_OK
        assert_database_invariants()

        # Step 11: Technician 2 restarts and completes (T8, T9)
        technician_client_2.post(
            f"/api/requests/{req_id}/transition/",
            {"action": "START_WORK", "expected_status": RequestStatus.REOPENED},
            format="json",
        )
        assert_database_invariants()

        technician_client_2.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "COMPLETE_WORK",
                "expected_status": RequestStatus.IN_PROGRESS,
                "note": "Fitted new fireproof thermal insulation wrap and secured with aluminium band.",
            },
            format="json",
        )
        assert_database_invariants()

        # Step 12: Supervisor verifies and closes (T10)
        resp_close = supervisor_client.post(
            f"/api/requests/{req_id}/transition/",
            {
                "action": "VERIFY_CLOSE",
                "expected_status": RequestStatus.WORK_COMPLETED,
                "note": "Inspected installation, confirmed insulation secured and pressure normal.",
            },
            format="json",
        )
        assert resp_close.status_code == status.HTTP_200_OK
        assert_database_invariants()

    @pytest.mark.parametrize("seed", range(5))
    def test_nt03_invariants_hold_after_random_operation_sequences(
        self,
        seed: int,
        resident_client: APIClient,
        supervisor_client: APIClient,
        technician_client: APIClient,
        technician_client_2: APIClient,
        technician_user: User,
        technician_user_2: User,
        location: Location,
        category: FaultCategory,
    ):
        """NT-03: random actions by random roles, legal or not, never break an invariant.

        The seed is fixed so that a failure can be reproduced exactly.
        """
        rng = random.Random(seed)
        request_ids = []
        for _ in range(4):
            created = resident_client.post(
                "/api/requests/",
                {
                    "location_id": location.id,
                    "category_id": category.id,
                    "description": "Random sequence test: a fault in the residence.",
                },
                format="json",
            )
            assert created.status_code == status.HTTP_201_CREATED
            request_ids.append(created.json()["id"])

        clients = [resident_client, supervisor_client, technician_client, technician_client_2]
        actions = [
            "REQUEST_CLARIFICATION",
            "PROVIDE_CLARIFICATION",
            "APPROVE",
            "REJECT",
            "ASSIGN",
            "REASSIGN",
            "START_WORK",
            "COMPLETE_WORK",
            "VERIFY_CLOSE",
            "REOPEN",
        ]
        audit_ids = assert_database_invariants()

        for _ in range(150):
            request_id = rng.choice(request_ids)
            current = MaintenanceRequest.objects.get(id=request_id).status
            response = rng.choice(clients).post(
                f"/api/requests/{request_id}/transition/",
                {
                    "action": rng.choice(actions),
                    "expected_status": current,
                    "note": "A long enough note for every action in this random test.",
                    "priority": Priority.MEDIUM,
                    "technician_id": rng.choice([technician_user.id, technician_user_2.id]),
                },
                format="json",
            )
            assert response.status_code in (200, 403, 404, 409, 422), response.content
            audit_ids = assert_database_invariants(audit_ids)
