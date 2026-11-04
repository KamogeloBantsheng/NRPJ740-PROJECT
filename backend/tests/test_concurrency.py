"""Concurrency & Pessimistic Locking Test Suite (Phase 10: TC-20, TC-23).

Validates Section 5.1 row locking (SELECT FOR UPDATE) and expected_status concurrency guards:
- TC-20: Concurrent Approve vs Reject on same request -> exactly 1 succeeds, other receives 409 Conflict.
- TC-23: 20 simultaneous Assign threads -> exactly 1 succeeds, 19 receive 409, exactly 1 active work order created.
"""

import concurrent.futures

import pytest
from apps.accounts.models import User
from apps.locations.models import FaultCategory, Location
from apps.workflow.models import MaintenanceRequest, Priority, RequestStatus, WorkOrder
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db(transaction=True)
class TestConcurrencyGuards:
    """Covers TC-20 and TC-23 with multi-threaded concurrent requests."""

    def test_tc20_simultaneous_approve_vs_reject_conflict(
        self,
        supervisor_user: User,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-20: Simultaneous approve vs reject on same request with expected_status guard (NFR-04).

        One operation acquires the row lock first and succeeds; the other detects status change and returns 409.
        """
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Urgent pipe burst leaking water into electrical cupboard.",
            status=RequestStatus.SUBMITTED,
        )

        def do_approve():
            # Dedicated client & connection per thread
            client = APIClient()
            client.force_authenticate(user=supervisor_user)
            resp = client.post(
                f"/api/requests/{req.id}/transition/",
                {
                    "action": "APPROVE",
                    "expected_status": RequestStatus.SUBMITTED,
                    "priority": Priority.CRITICAL,
                },
                format="json",
            )
            connection.close()
            return ("APPROVE", resp.status_code, resp.json())

        def do_reject():
            client = APIClient()
            client.force_authenticate(user=supervisor_user)
            resp = client.post(
                f"/api/requests/{req.id}/transition/",
                {
                    "action": "REJECT",
                    "expected_status": RequestStatus.SUBMITTED,
                    "note": "Duplicate maintenance request filed by another resident.",
                },
                format="json",
            )
            connection.close()
            return ("REJECT", resp.status_code, resp.json())

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(do_approve)
            fut2 = executor.submit(do_reject)
            results = [fut1.result(), fut2.result()]

        status_codes = [r[1] for r in results]
        assert status.HTTP_200_OK in status_codes
        assert status.HTTP_409_CONFLICT in status_codes

        # Verify exactly one 200 and exactly one 409
        assert status_codes.count(status.HTTP_200_OK) == 1
        assert status_codes.count(status.HTTP_409_CONFLICT) == 1

        # Database state reflects winning operation
        req.refresh_from_db()
        assert req.status in (RequestStatus.APPROVED, RequestStatus.REJECTED)

    def test_tc23_twenty_simultaneous_assignments_fifty_times(
        self,
        supervisor_user: User,
        technician_user: User,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-23: 20 simultaneous assignments of one request, repeated 50 times (NFR-04).

        Every run must give exactly one success, 19 conflicts and one active work order.
        """

        def attempt_assign(request_id: int) -> int:
            client = APIClient()
            client.force_authenticate(user=supervisor_user)
            resp = client.post(
                f"/api/requests/{request_id}/transition/",
                {
                    "action": "ASSIGN",
                    "expected_status": RequestStatus.APPROVED,
                    "technician_id": technician_user.id,
                },
                format="json",
            )
            connection.close()
            return resp.status_code

        num_threads = 20
        for _ in range(50):
            req = MaintenanceRequest.objects.create(
                resident=resident_user,
                location=location,
                category=category,
                description="Elevator door sensor failure causing intermittent stoppage.",
                status=RequestStatus.APPROVED,
                priority=Priority.HIGH,
            )

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                status_codes = list(executor.map(attempt_assign, [req.id] * num_threads))

            assert status_codes.count(status.HTTP_200_OK) == 1
            assert status_codes.count(status.HTTP_409_CONFLICT) == num_threads - 1

            active_orders = WorkOrder.objects.filter(request=req, ended_at__isnull=True)
            assert active_orders.count() == 1
            assert active_orders.first().technician_id == technician_user.id

            req.refresh_from_db()
            assert req.status == RequestStatus.ASSIGNED
