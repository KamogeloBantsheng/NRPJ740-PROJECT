"""User Administration & CSV Batch Import Test Suite (Phase 10: TC-06 to TC-09).

Verifies account lifecycle guards (BR-07: cannot deactivate technician with active work,
cannot remove last admin) and all-or-nothing CSV batch import (FR-04, NFR-03, TC-07 to TC-09).
"""

import io

import pytest
from apps.accounts.models import Role, User
from apps.audit.models import AuditAction, AuditEvent
from apps.locations.models import FaultCategory, Location, Residence
from apps.workflow.models import MaintenanceRequest, RequestStatus, WorkOrder
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestUserAdministration:
    """Covers TC-06 to TC-09."""

    def test_tc06_cannot_deactivate_technician_with_active_work_order(
        self,
        admin_client: APIClient,
        technician_user: User,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-06 Part A: Deactivating a technician with active work orders returns 409 Conflict (FR-03, BR-07)."""
        # Create an active request and assign work order to technician
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Leaking pipe in bathroom requiring urgent plumbing repair",
            status=RequestStatus.ASSIGNED,
            priority="HIGH",
        )
        WorkOrder.objects.create(
            request=req,
            technician=technician_user,
            assigned_by=resident_user,  # actor
        )

        # Admin attempts to deactivate the technician
        resp = admin_client.patch(
            f"/api/users/{technician_user.id}/",
            {"is_active": False},
            format="json",
        )
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert "Cannot deactivate a technician with active work orders" in resp.json()["message"]

        # Verify technician is still active
        technician_user.refresh_from_db()
        assert technician_user.is_active is True

    def test_tc06_cannot_demote_or_deactivate_last_admin(
        self, admin_client: APIClient, admin_user: User
    ):
        """TC-06 Part B: Demoting or deactivating the last active Admin returns 409 Conflict (FR-03, BR-07)."""
        # Ensure only 1 active admin exists
        User.objects.filter(role=Role.ADMIN).exclude(id=admin_user.id).delete()
        assert User.objects.filter(role=Role.ADMIN, is_active=True).count() == 1

        # Attempt A: Deactivate last admin
        resp_deact = admin_client.patch(
            f"/api/users/{admin_user.id}/",
            {"is_active": False},
            format="json",
        )
        assert resp_deact.status_code == status.HTTP_409_CONFLICT
        assert "Cannot deactivate the last active administrator" in resp_deact.json()["message"]

        # Attempt B: Change role of last admin to Supervisor
        resp_demote = admin_client.patch(
            f"/api/users/{admin_user.id}/",
            {"role": Role.SUPERVISOR},
            format="json",
        )
        assert resp_demote.status_code == status.HTTP_409_CONFLICT
        assert "Cannot demote the last active administrator" in resp_demote.json()["message"]

        # Verify admin still admin and active
        admin_user.refresh_from_db()
        assert admin_user.role == Role.ADMIN
        assert admin_user.is_active is True

    def test_tc07_valid_csv_import_creates_accounts_and_credentials_file(
        self, admin_client: APIClient, residence: Residence
    ):
        """TC-07: Valid CSV of N rows creates N accounts, returns one-time credentials (FR-04, AC-04.1)."""
        csv_content = (
            "full_name,email,student_number\n"
            "Alice Mokoena,alice.m@spu.ac.za,202300001\n"
            "Bob Dlamini,bob.d@spu.ac.za,202300002\n"
            "Charlie Botha,charlie.b@spu.ac.za,202300003\n"
        )
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "residents.csv"

        resp = admin_client.post(
            "/api/users/import-csv/",
            {"file": csv_file},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["created_count"] == 3
        assert len(data["credentials"]) == 3
        names = [u["full_name"] for u in data["credentials"]]
        assert "Alice Mokoena" in names
        assert "Bob Dlamini" in names
        assert "Charlie Botha" in names

        # Verify users exist in database with temporary passwords
        u = User.objects.get(email="alice.m@spu.ac.za")
        assert u.role == Role.RESIDENT
        assert u.must_change_password is True
        assert u.student_number == "202300001"

        # Verify audit event
        audit = AuditEvent.objects.filter(
            action=AuditAction.USER_IMPORTED,
            details__total_imported=3,
        ).first()
        assert audit is not None

    def test_tc08_csv_import_with_invalid_row_aborts_all_or_nothing(
        self, admin_client: APIClient, resident_user: User
    ):
        """TC-08: CSV with invalid row/duplicate creates 0 accounts and lists all errors (FR-04, AC-04.2)."""
        # Row 1 is valid, Row 2 has duplicate email of existing user, Row 3 has invalid email format
        csv_content = (
            "full_name,email,student_number,room_number\n"
            "David Van Wyk,david.vw@spu.ac.za,202300004,104\n"
            f"Duplicate Resident,{resident_user.email},202300005,105\n"
            "Eva Malan,not-an-email,202300006,106\n"
        )
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "residents.csv"

        resp = admin_client.post(
            "/api/users/import-csv/",
            {"file": csv_file},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = resp.json()
        assert "fields" in data
        bad_rows = data["fields"]["bad_rows"]
        assert len(bad_rows) >= 2
        bad_row_nums = [item["row"] for item in bad_rows]
        assert 3 in bad_row_nums  # Row 2 in CSV data = row 3 in 1-based index (with header)
        assert 4 in bad_row_nums  # Row 3 in CSV data = row 4 in 1-based index

        # Verify all-or-nothing rollback: David Van Wyk was NOT created
        assert not User.objects.filter(email="david.vw@spu.ac.za").exists()

    def test_tc09_csv_import_size_limit_and_non_admin_forbidden(
        self, admin_client: APIClient, resident_client: APIClient
    ):
        """TC-09: CSV exceeding 2MB/2,000 rows rejected before processing; non-Admin returns 403 (FR-04, AC-04.3)."""
        # Non-admin forbidden
        csv_file = io.BytesIO(b"full_name,email,student_number,room_number\n")
        csv_file.name = "test.csv"
        forbidden_resp = resident_client.post(
            "/api/users/import-csv/",
            {"file": csv_file},
            format="multipart",
        )
        assert forbidden_resp.status_code == status.HTTP_403_FORBIDDEN

        # Size limit: > 2,000 rows rejected
        large_rows = ["full_name,email,student_number\n"]
        for i in range(2001):
            large_rows.append(f"Student {i},student{i}@spu.ac.za,2023{i:05d}\n")
        large_csv = io.BytesIO("".join(large_rows).encode("utf-8"))
        large_csv.name = "too_large.csv"

        size_resp = admin_client.post(
            "/api/users/import-csv/",
            {"file": large_csv},
            format="multipart",
        )
        assert size_resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "exceeds the maximum allowed row count" in size_resp.json()["message"]
