"""TC-35 and NT-01: exhaustive matrices generated from the rules, not hand-picked cases."""

import pytest
from apps.accounts.models import Role
from apps.workflow.models import MaintenanceRequest, Priority, RequestStatus, WorkOrder
from apps.workflow.rules import TABLE_5_1_RULES
from django.utils import timezone
from rest_framework.test import APIClient

ACTIONS = sorted({rule["action"] for rule in TABLE_5_1_RULES if rule["action"] != "SUBMIT"})
LEGAL = {(rule["from_status"], rule["action"]): rule for rule in TABLE_5_1_RULES if rule["from_status"]}
ACTIVE_WORK = {
    RequestStatus.ASSIGNED,
    RequestStatus.IN_PROGRESS,
    RequestStatus.WORK_COMPLETED,
    RequestStatus.REOPENED,
}
NEEDS_PRIORITY = ACTIVE_WORK | {RequestStatus.APPROVED, RequestStatus.VERIFIED_CLOSED}
TERMINAL = {RequestStatus.REJECTED, RequestStatus.VERIFIED_CLOSED}


@pytest.fixture
def clients(resident_user, technician_user, supervisor_user, warden_user, admin_user) -> dict[str, APIClient]:
    users = {
        Role.RESIDENT: resident_user,
        Role.TECHNICIAN: technician_user,
        Role.SUPERVISOR: supervisor_user,
        Role.WARDEN: warden_user,
        Role.ADMIN: admin_user,
    }
    result = {}
    for role, user in users.items():
        result[role] = APIClient(raise_request_exception=False)
        result[role].force_login(user)
    return result


@pytest.mark.django_db
def test_tc35_every_state_action_role_combination(
    clients, resident_user, technician_user, technician_user_2, supervisor_user, location, category
):
    """TC-35: legal combinations from Table 5.1 succeed; every other one is refused and changes nothing."""
    checked = 0
    for status in RequestStatus.values:
        for action in ACTIONS:
            for role, client in clients.items():
                req = MaintenanceRequest.objects.create(
                    resident=resident_user,
                    location=location,
                    category=category,
                    description="A fault used by the transition matrix test.",
                    status=status,
                    priority=Priority.LOW if status in NEEDS_PRIORITY else None,
                    closed_at=timezone.now() if status in TERMINAL else None,
                )
                if status in ACTIVE_WORK:
                    WorkOrder.objects.create(request=req, technician=technician_user, assigned_by=supervisor_user)

                response = client.post(
                    f"/api/requests/{req.id}/transition/",
                    {
                        "action": action,
                        "expected_status": status,
                        "note": "A note long enough for every action in the table.",
                        "priority": Priority.HIGH,
                        "technician_id": technician_user_2.id,
                    },
                    format="json",
                )

                rule = LEGAL.get((status, action))
                role_is_right = next(r["actor_role"] for r in TABLE_5_1_RULES if r["action"] == action) == role
                label = f"{status} {action} {role}"
                req.refresh_from_db()

                if rule and role_is_right:
                    assert response.status_code == 200, f"{label}: {response.content}"
                    assert req.status == rule["to_status"], label
                else:
                    assert response.status_code in (403, 404, 409), f"{label}: {response.status_code}"
                    assert req.status == status, label
                    if role_is_right and role != Role.TECHNICIAN:
                        assert response.status_code == 409, label
                    if not role_is_right and role != Role.TECHNICIAN:
                        assert response.status_code == 403, label
                checked += 1

    assert checked == len(RequestStatus.values) * len(ACTIONS) * len(clients)


# Every read endpoint and the roles it allows
ENDPOINTS = {
    "/api/me": set(Role.values),
    "/api/requests/": set(Role.values),
    "/api/locations/": set(Role.values),
    "/api/categories/": set(Role.values),
    "/api/residences/": {Role.SUPERVISOR, Role.ADMIN},
    "/api/triage-queue/": {Role.SUPERVISOR},
    "/api/technicians/": {Role.SUPERVISOR},
    "/api/work-queue/": {Role.TECHNICIAN},
    "/api/dashboard/": {Role.SUPERVISOR, Role.WARDEN},
    "/api/users/": {Role.ADMIN},
    "/api/audit-logs/": {Role.ADMIN},
}


@pytest.mark.django_db
@pytest.mark.parametrize("path", ENDPOINTS)
def test_nt01_every_endpoint_for_every_role(clients, path):
    """NT-01: a role that is allowed gets 200, any other gets 403, and no session gets 401."""
    assert APIClient(raise_request_exception=False).get(path).status_code == 401
    for role, client in clients.items():
        expected = 200 if role in ENDPOINTS[path] else 403
        assert client.get(path).status_code == expected, f"{path} as {role}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/api/requests/", {Role.RESIDENT, Role.WARDEN}),
        ("/api/users/", {Role.ADMIN}),
        ("/api/users/import-csv/", {Role.ADMIN}),
    ],
)
def test_nt01_write_endpoints_refuse_other_roles(clients, path, allowed):
    """NT-01: an empty body reaches validation only for permitted roles."""
    assert APIClient(raise_request_exception=False).post(path, {}, format="json").status_code == 401
    for role, client in clients.items():
        status = client.post(path, {}, format="json").status_code
        if role in allowed:
            assert status not in (401, 403, 500), f"{path} as {role}"
        else:
            assert status == 403, f"{path} as {role}"


@pytest.mark.django_db
def test_nt01_out_of_scope_objects_are_not_found(
    clients, resident_user, resident_user_2, supervisor_user, technician_user_2, location, category
):
    """NT-01: a request outside the caller's scope is reported as not found."""
    req = MaintenanceRequest.objects.create(
        resident=resident_user_2,
        location=location,
        category=category,
        description="Another resident's request for the scope test.",
        status=RequestStatus.ASSIGNED,
        priority=Priority.LOW,
    )
    WorkOrder.objects.create(request=req, technician=technician_user_2, assigned_by=supervisor_user)

    for role in (Role.RESIDENT, Role.TECHNICIAN):
        assert clients[role].get(f"/api/requests/{req.id}/").status_code == 404
        assert clients[role].get(f"/api/requests/{req.id}/timeline/").status_code == 404
