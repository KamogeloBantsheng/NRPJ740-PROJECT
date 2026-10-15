"""Database Constraints, Triggers & Atomicity Test Suite (Phase 10: TC-24, TC-25, TC-39, NT-06).

Validates physical PostgreSQL schema constraints, append-only tamper triggers,
partial unique indexes (INV-1), and transactional atomicity.
"""

import pytest
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.locations.models import FaultCategory, Location, Residence
from apps.workflow.models import MaintenanceRequest, Priority, RequestStatus, WorkOrder
from django.db import DatabaseError, IntegrityError, ProgrammingError, connection, transaction


@pytest.mark.django_db
class TestDatabaseInvariantsAndConstraints:
    """Covers TC-24, TC-25, TC-39, NT-06."""

    def test_tc24_fault_injection_atomicity_rollback(
        self,
        resident_user: User,
        supervisor_user: User,
        technician_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-24: Fault injection between work order insert and commit -> atomic transaction rollback (AC-06.3)."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Power outlet in kitchen sparking under load.",
            status=RequestStatus.APPROVED,
            priority=Priority.HIGH,
        )

        initial_wo_count = WorkOrder.objects.filter(request=req).count()

        # Simulate exception during assignment transaction
        with pytest.raises(RuntimeError, match="Simulated network fault before commit"):
            with transaction.atomic():
                WorkOrder.objects.create(
                    request=req,
                    technician=technician_user,
                    assigned_by=supervisor_user,
                )
                req.status = RequestStatus.ASSIGNED
                req.save()
                # Fault injected before transaction commit
                raise RuntimeError("Simulated network fault before commit")

        # Verify atomic rollback
        req.refresh_from_db()
        assert req.status == RequestStatus.APPROVED
        assert WorkOrder.objects.filter(request=req).count() == initial_wo_count

    def test_tc25_partial_unique_index_one_active_work_order(
        self,
        resident_user: User,
        supervisor_user: User,
        technician_user: User,
        technician_user_2: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-25: Direct SQL insert of second active work order rejected (INV-1)."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Broken window glass in communal hall.",
            status=RequestStatus.ASSIGNED,
            priority=Priority.MEDIUM,
        )

        # First active work order succeeds
        WorkOrder.objects.create(
            request=req,
            technician=technician_user,
            assigned_by=supervisor_user,
            ended_at=None,
        )

        # Attempting second active work order for the same request violates partial unique index
        with pytest.raises(IntegrityError):
            WorkOrder.objects.create(
                request=req,
                technician=technician_user_2,
                assigned_by=supervisor_user,
                ended_at=None,
            )

    def test_tc39_direct_sql_tamper_rejected_on_audit_logs(
        self,
        resident_user: User,
    ):
        """TC-39: Direct SQL UPDATE, DELETE, and TRUNCATE rejected by append-only triggers (NFR-05, AC-17.2)."""
        # 1. Attempt TRUNCATE before any inserts -> rejected by trg_audit_logs_no_truncate
        with pytest.raises((ProgrammingError, DatabaseError), match="audit_logs table is append-only"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("TRUNCATE audit_logs;")

        # Create an audit event for row-level trigger tests
        audit = AuditEvent.objects.create(
            action=AuditAction.LOGIN_FAILED,
            actor=resident_user,
            details={"attempt": 1},
        )

        # 2. Attempt UPDATE -> rejected by trg_audit_logs_no_update_delete
        with pytest.raises((ProgrammingError, DatabaseError), match="audit_logs table is append-only"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE audit_logs SET note = 'Tampered' WHERE id = %s;",
                        [audit.id],
                    )

        # 3. Attempt DELETE -> rejected by trg_audit_logs_no_update_delete
        with pytest.raises((ProgrammingError, DatabaseError), match="audit_logs table is append-only"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM audit_logs WHERE id = %s;",
                        [audit.id],
                    )

    def test_nt06_physical_constraints_violation_rejected(
        self,
        resident_user: User,
        residence: Residence,
        location: Location,
        category: FaultCategory,
    ):
        """NT-06: Direct SQL violation of CHECK, FOREIGN KEY, and UNIQUE constraints rejected with IntegrityError."""
        # 1. CHECK constraint violation: invalid request status
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO maintenance_requests
                            (description, status, client_token, resident_id,
                             location_id, category_id, created_at, updated_at)
                        VALUES
                            ('Valid test description', 'INVALID_STATUS', gen_random_uuid(), %s, %s, %s, now(), now());
                        """,
                        [resident_user.id, location.id, category.id],
                    )

        # 2. CHECK constraint violation: resident without student_number
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users
                            (email, full_name, role, password, must_change_password,
                             is_active, created_at, residence_id)
                        VALUES
                            ('nostudent@spu.ac.za', 'No Student', 'RESIDENT', 'argon2...', false, true, now(), %s);
                        """,
                        [residence.id],
                    )

        # 3. FOREIGN KEY violation: non-existent location ID (immediate enforcement)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE;")
                    cursor.execute(
                        """
                        INSERT INTO maintenance_requests
                            (description, status, client_token, resident_id,
                             location_id, category_id, created_at, updated_at)
                        VALUES
                            ('Valid test description', 'SUBMITTED', gen_random_uuid(), %s, 999999, %s, now(), now());
                        """,
                        [resident_user.id, category.id],
                    )

        # 4. UNIQUE constraint violation: duplicate residence name
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Residence.objects.create(name=residence.name)
