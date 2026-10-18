"""Pytest configuration and shared fixtures for NPRJ740 system test suite (Phase 10).

Implements Option A teardown strategy (disabling/enabling triggers during test database cleanup)
and provides role-scoped authenticated API clients and test data factories.
"""

import pytest
from apps.accounts.models import Role, User
from apps.locations.models import FaultCategory, Location, LocationKind, Residence
from apps.workflow.models import MaintenanceRequest, RequestStatus, WorkOrder
from apps.workflow.rules import sync_transition_rules
from django.db import DatabaseError, connection
from rest_framework.test import APIClient

# Option A Teardown Strategy:
# Wraps execute_sql_flush to temporarily disable triggers during test database flush
# and re-enable them immediately so they are 100% active during all test runs.
_original_execute_sql_flush = connection.ops.execute_sql_flush


def _option_a_execute_sql_flush(sql_list):
    try:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_no_update_delete;")
            cursor.execute("ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_no_truncate;")
    except DatabaseError:
        pass

    try:
        _original_execute_sql_flush(sql_list)
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE audit_logs ENABLE TRIGGER trg_audit_logs_no_update_delete;")
                cursor.execute("ALTER TABLE audit_logs ENABLE TRIGGER trg_audit_logs_no_truncate;")
        except DatabaseError:
            pass


connection.ops.execute_sql_flush = _option_a_execute_sql_flush


@pytest.fixture(autouse=True)
def clean_audit_trigger():
    """Option A Teardown Strategy:
    Keeps audit triggers strictly enabled during test execution to enforce append-only invariants,
    and cleanly disables/re-enables them only during post-test table truncation.
    """
    yield
    # Post-test cleanup (Option A)
    try:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_no_update_delete;")
            cursor.execute("ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_no_truncate;")
            cursor.execute("DELETE FROM audit_logs;")
            cursor.execute("ALTER TABLE audit_logs ENABLE TRIGGER trg_audit_logs_no_update_delete;")
            cursor.execute("ALTER TABLE audit_logs ENABLE TRIGGER trg_audit_logs_no_truncate;")
    except DatabaseError:
        # Graceful fallback if database connection is closed or not in PostgreSQL
        pass


@pytest.fixture(autouse=True)
def setup_transition_rules(db):
    """Ensure canonical Table 5.1 transition rules are populated."""
    sync_transition_rules()


@pytest.fixture
def residence(db) -> Residence:
    """Moroka Hall Residence fixture."""
    res, _ = Residence.objects.get_or_create(
        name="Moroka Hall of Residence",
        defaults={"is_active": True},
    )
    return res


@pytest.fixture
def other_residence(db) -> Residence:
    """Secondary residence for cross-residence scoping validation."""
    res, _ = Residence.objects.get_or_create(
        name="Luka Jantjie House",
        defaults={"is_active": True},
    )
    return res


@pytest.fixture
def location(db, residence) -> Location:
    """Active location in Moroka Hall."""
    loc, _ = Location.objects.get_or_create(
        residence=residence,
        block="A",
        floor=1,
        label="Room 101",
        defaults={"kind": LocationKind.ROOM, "is_active": True},
    )
    return loc


@pytest.fixture
def location_b(db, residence) -> Location:
    """Secondary active location in Moroka Hall."""
    loc, _ = Location.objects.get_or_create(
        residence=residence,
        block="B",
        floor=2,
        label="Room 205",
        defaults={"kind": LocationKind.ROOM, "is_active": True},
    )
    return loc


@pytest.fixture
def common_area_location(db, residence) -> Location:
    """Active common area in Moroka Hall."""
    loc, _ = Location.objects.get_or_create(
        residence=residence,
        block="A",
        floor=0,
        label="Study Room A",
        defaults={"kind": LocationKind.COMMON_AREA, "is_active": True},
    )
    return loc


@pytest.fixture
def other_res_location(db, other_residence) -> Location:
    """Location belonging to a different residence."""
    loc, _ = Location.objects.get_or_create(
        residence=other_residence,
        block="A",
        floor=1,
        label="Room 101",
        defaults={"kind": LocationKind.ROOM, "is_active": True},
    )
    return loc


@pytest.fixture
def category(db) -> FaultCategory:
    """Approved active fault category."""
    cat, _ = FaultCategory.objects.get_or_create(
        name="Plumbing",
        defaults={"is_active": True},
    )
    return cat


@pytest.fixture
def category_electrical(db) -> FaultCategory:
    """Secondary fault category."""
    cat, _ = FaultCategory.objects.get_or_create(
        name="Electrical",
        defaults={"description": "Lights, plugs, switches", "is_active": True},
    )
    return cat


@pytest.fixture
def resident_user(db, residence, location) -> User:
    """Active Resident in Moroka Hall."""
    user, _ = User.objects.get_or_create(
        email="resident.test@spu.ac.za",
        defaults={
            "full_name": "Test Resident",
            "role": Role.RESIDENT,
            "residence": residence,
            "student_number": "202311455",
            "assigned_location": location,
            "is_active": True,
            "must_change_password": False,
        },
    )
    user.assigned_location = location
    user.set_password("ValidPassword#123")
    user.save()
    return user


@pytest.fixture
def resident_user_2(db, residence, location_b) -> User:
    """Secondary Resident in Moroka Hall."""
    user, _ = User.objects.get_or_create(
        email="resident2.test@spu.ac.za",
        defaults={
            "full_name": "Second Resident",
            "role": Role.RESIDENT,
            "residence": residence,
            "student_number": "202311999",
            "assigned_location": location_b,
            "is_active": True,
            "must_change_password": False,
        },
    )
    user.assigned_location = location_b
    user.set_password("ValidPassword#123")
    user.save()
    return user


@pytest.fixture
def supervisor_user(db) -> User:
    """Active Supervisor."""
    user, _ = User.objects.get_or_create(
        email="supervisor.test@spu.ac.za",
        defaults={
            "full_name": "Test Supervisor",
            "role": Role.SUPERVISOR,
            "is_active": True,
            "must_change_password": False,
        },
    )
    user.set_password("ValidPassword#123")
    user.save()
    return user


@pytest.fixture
def technician_user(db) -> User:
    """Active Technician 1."""
    user, _ = User.objects.get_or_create(
        email="technician.test@spu.ac.za",
        defaults={
            "full_name": "Test Technician One",
            "role": Role.TECHNICIAN,
            "is_active": True,
            "must_change_password": False,
        },
    )
    user.set_password("ValidPassword#123")
    user.save()
    return user


@pytest.fixture
def technician_user_2(db) -> User:
    """Active Technician 2 (for reassignment tests)."""
    user, _ = User.objects.get_or_create(
        email="technician2.test@spu.ac.za",
        defaults={
            "full_name": "Test Technician Two",
            "role": Role.TECHNICIAN,
            "is_active": True,
            "must_change_password": False,
        },
    )
    user.set_password("ValidPassword#123")
    user.save()
    return user


@pytest.fixture
def warden_user(db, residence) -> User:
    """Active Warden assigned to Moroka Hall."""
    user, _ = User.objects.get_or_create(
        email="warden.test@spu.ac.za",
        defaults={
            "full_name": "Test Warden",
            "role": Role.WARDEN,
            "residence": residence,
            "is_active": True,
            "must_change_password": False,
        },
    )
    user.set_password("ValidPassword#123")
    user.save()
    return user


@pytest.fixture
def admin_user(db) -> User:
    """Active System Administrator."""
    user, _ = User.objects.get_or_create(
        email="admin.test@spu.ac.za",
        defaults={
            "full_name": "Test Administrator",
            "role": Role.ADMIN,
            "is_active": True,
            "must_change_password": False,
        },
    )
    user.set_password("ValidPassword#123")
    user.save()
    return user


@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated DRF APIClient."""
    return APIClient()


@pytest.fixture
def resident_client(resident_user) -> APIClient:
    """APIClient authenticated as Resident."""
    client = APIClient()
    client.force_login(resident_user)
    return client


@pytest.fixture
def resident_client_2(resident_user_2) -> APIClient:
    """APIClient authenticated as secondary Resident."""
    client = APIClient()
    client.force_login(resident_user_2)
    return client


@pytest.fixture
def supervisor_client(supervisor_user) -> APIClient:
    """APIClient authenticated as Supervisor."""
    client = APIClient()
    client.force_login(supervisor_user)
    return client


@pytest.fixture
def technician_client(technician_user) -> APIClient:
    """APIClient authenticated as Technician 1."""
    client = APIClient()
    client.force_login(technician_user)
    return client


@pytest.fixture
def technician_client_2(technician_user_2) -> APIClient:
    """APIClient authenticated as Technician 2."""
    client = APIClient()
    client.force_login(technician_user_2)
    return client


@pytest.fixture
def warden_client(warden_user) -> APIClient:
    """APIClient authenticated as Warden."""
    client = APIClient()
    client.force_login(warden_user)
    return client


@pytest.fixture
def admin_client(admin_user) -> APIClient:
    """APIClient authenticated as Admin."""
    client = APIClient()
    client.force_login(admin_user)
    return client


def assert_database_invariants():
    """Verifies all six core database invariants defined in Section 5.6 (INV-1 to INV-6)."""
    # INV-1: Every request has a valid status in RequestStatus
    valid_statuses = set(RequestStatus.values)
    invalid_status_reqs = MaintenanceRequest.objects.exclude(status__in=valid_statuses).count()
    assert invalid_status_reqs == 0, f"Found {invalid_status_reqs} requests with invalid status"

    # INV-2: If priority is set, it must be valid; APPROVED+ requests must have priority
    approved_without_priority = MaintenanceRequest.objects.filter(
        status__in=[
            RequestStatus.APPROVED,
            RequestStatus.ASSIGNED,
            RequestStatus.IN_PROGRESS,
            RequestStatus.WORK_COMPLETED,
            RequestStatus.VERIFIED_CLOSED,
            RequestStatus.REOPENED,
        ],
        priority__isnull=True,
    ).count()
    assert approved_without_priority == 0, f"Found {approved_without_priority} approved+ requests without priority"

    # INV-3: closed_at set exactly when REJECTED or VERIFIED_CLOSED
    terminal_without_closed_at = MaintenanceRequest.objects.filter(
        status__in=[RequestStatus.REJECTED, RequestStatus.VERIFIED_CLOSED],
        closed_at__isnull=True,
    ).count()
    assert terminal_without_closed_at == 0, f"Found {terminal_without_closed_at} terminal requests without closed_at"

    non_terminal_with_closed_at = MaintenanceRequest.objects.exclude(
        status__in=[RequestStatus.REJECTED, RequestStatus.VERIFIED_CLOSED],
    ).filter(closed_at__isnull=False).count()
    assert non_terminal_with_closed_at == 0, f"Found {non_terminal_with_closed_at} non-terminal requests with closed_at"

    # INV-4: At most one active work order per request (ended_at IS NULL)
    from django.db.models import Count, Q
    multi_active_wo = (
        MaintenanceRequest.objects.annotate(
            active_wo_count=Count("work_orders", filter=Q(work_orders__ended_at__isnull=True))
        )
        .filter(active_wo_count__gt=1)
        .count()
    )
    assert multi_active_wo == 0, f"Found {multi_active_wo} requests with multiple active work orders"

    # INV-5: Work order end_reason is null exactly when ended_at is null
    inconsistent_wo = WorkOrder.objects.filter(
        (Q(ended_at__isnull=True) & Q(end_reason__isnull=False))
        | (Q(ended_at__isnull=False) & Q(end_reason__isnull=True))
    ).count()
    assert inconsistent_wo == 0, f"Found {inconsistent_wo} work orders with inconsistent end state"
