"""Pytest configuration and shared fixtures for NPRJ740 system test suite (Phase 10).

Implements Option A teardown strategy (disabling/enabling triggers during test database cleanup)
and provides role-scoped authenticated API clients and test data factories.
"""

import pytest
from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.locations.models import FaultCategory, Location, LocationKind, Residence
from apps.workflow.models import MaintenanceRequest, RequestStatus
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
        defaults={"is_active": True},
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


def assert_database_invariants(known_audit_ids: set[int] | None = None) -> set[int]:
    """Check INV-1 to INV-6 from report Section 5.6 and return the audit ids now present.

    Pass the ids from the previous call so INV-6 can prove no event has disappeared.
    """
    active_states = {
        RequestStatus.ASSIGNED,
        RequestStatus.IN_PROGRESS,
        RequestStatus.WORK_COMPLETED,
        RequestStatus.REOPENED,
    }
    terminal_states = {RequestStatus.REJECTED, RequestStatus.VERIFIED_CLOSED}
    needs_priority = active_states | {RequestStatus.APPROVED, RequestStatus.VERIFIED_CLOSED}

    for req in MaintenanceRequest.objects.select_related("location", "resident"):
        active_orders = list(req.work_orders.filter(ended_at__isnull=True).select_related("technician"))

        # INV-1: an active work order exists exactly in these states, and never more than one
        expected = 1 if req.status in active_states else 0
        assert len(active_orders) == expected, f"INV-1: {req.tracking_number} {req.status} has {len(active_orders)}"

        # INV-2: the latest status-changing audit event matches the current status
        latest = AuditEvent.objects.filter(request_id=req.id).exclude(to_status=None).order_by("-id").first()
        assert latest is not None and latest.to_status == req.status, f"INV-2: {req.tracking_number}"

        # INV-3: the Technician on an active work order is an active Technician
        for order in active_orders:
            assert order.technician.role == Role.TECHNICIAN, f"INV-3: {req.tracking_number}"
            assert order.technician.is_active, f"INV-3: {req.tracking_number}"

        # INV-4: the Location is in the reporter's residence
        assert req.location.residence_id == req.resident.residence_id, f"INV-4: {req.tracking_number}"

        # INV-5: priority is set once approved, and closed_at exactly for terminal states
        if req.status in needs_priority:
            assert req.priority is not None, f"INV-5: {req.tracking_number} has no priority"
        assert (req.closed_at is not None) == (req.status in terminal_states), f"INV-5: {req.tracking_number}"

    # INV-6: no audit event is ever removed
    audit_ids = set(AuditEvent.objects.values_list("id", flat=True))
    if known_audit_ids is not None:
        assert known_audit_ids <= audit_ids, "INV-6: an audit event disappeared"
    return audit_ids
