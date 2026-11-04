"""Regression tests for defects found by the system audit (report Section 7.4).

Each test states the behaviour the report requires. Every one of these failed, or returned a
server error, before the matching fix.
"""

import concurrent.futures
import io
import json
import uuid

import pytest
from apps.accounts.models import Role, User
from apps.accounts.services import AuthService, get_client_ip
from apps.audit.models import AuditAction, AuditEvent
from apps.workflow.models import MaintenanceRequest, Priority, RequestStatus, WorkOrder
from django.core.management import call_command
from django.db import connection
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

PASSWORD = "ValidPassword#123"


def client_for(user: User | None = None) -> APIClient:
    """A client that reports server errors as responses, so a 500 fails the assertion."""
    client = APIClient(raise_request_exception=False)
    if user:
        client.force_login(user)
    return client


def make_request(resident, location, category, request_status=RequestStatus.SUBMITTED, priority=None, closed=False):
    return MaintenanceRequest.objects.create(
        resident=resident,
        location=location,
        category=category,
        description="Leaking tap in the bathroom basin area.",
        status=request_status,
        priority=priority,
        closed_at=timezone.now() if closed else None,
    )


def upload(client: APIClient, content: bytes):
    file = io.BytesIO(content)
    file.name = "users.csv"
    return client.post("/api/users/import-csv/", {"file": file}, format="multipart")


@pytest.mark.django_db
class TestAuthentication:
    def test_temporary_password_blocks_the_api_until_changed(self, resident_user, location, category):
        """FR-02: the forced change is enforced by the server, not only the browser."""
        resident_user.must_change_password = True
        resident_user.save()
        client = client_for()
        login = client.post("/api/auth/login", {"email": resident_user.email, "password": PASSWORD}, format="json")
        assert login.status_code == status.HTTP_200_OK

        blocked = client.get("/api/requests/")
        assert blocked.status_code == status.HTTP_403_FORBIDDEN
        assert blocked.json()["code"] == "PASSWORD_CHANGE_REQUIRED"
        submit = client.post(
            "/api/requests/",
            {"location_id": location.id, "category_id": category.id, "description": "Must be blocked for now."},
            format="json",
        )
        assert submit.status_code == status.HTTP_403_FORBIDDEN
        assert MaintenanceRequest.objects.count() == 0

        assert client.get("/api/me").status_code == status.HTTP_200_OK
        changed = client.post(
            "/api/auth/password",
            {"current_password": PASSWORD, "new_password": "BrandNewSecret#2026"},
            format="json",
        )
        assert changed.status_code == status.HTTP_200_OK
        assert client.get("/api/requests/").status_code == status.HTTP_200_OK

    def test_throttle_counts_one_account_for_one_minute(self, resident_user):
        """AC-01.3: 5 failures give 429 for the next attempt, and only inside the window."""
        client = client_for()
        codes = [
            client.post(
                "/api/auth/login", {"email": resident_user.email, "password": "wrong"}, format="json"
            ).status_code
            for _ in range(6)
        ]
        assert codes == [401, 401, 401, 401, 401, 429]

        # Move the failures out of the window. The trigger protects the rows, so the clock moves instead.
        later = timezone.now() + timezone.timedelta(seconds=61)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(timezone, "now", lambda: later)
            retry = client.post("/api/auth/login", {"email": resident_user.email, "password": PASSWORD}, format="json")
        assert retry.status_code == status.HTTP_200_OK

    def test_old_failures_never_escalate_into_a_long_lockout(self, resident_user):
        """Report: the throttle lasts one minute, however many failures happened earlier that day."""
        for _ in range(25):
            AuditEvent.objects.create(
                action=AuditAction.LOGIN_FAILED,
                occurred_at=timezone.now() - timezone.timedelta(minutes=5),
                details={"email": resident_user.email, "ip_address": "127.0.0.1"},
            )
        login = client_for().post(
            "/api/auth/login", {"email": resident_user.email, "password": PASSWORD}, format="json"
        )
        assert login.status_code == status.HTTP_200_OK

    def test_failures_for_other_accounts_count_only_against_the_ip(self, resident_user, resident_user_2):
        """NFR-02: another IP is unaffected when one IP is throttled."""
        for _ in range(5):
            client_for().post("/api/auth/login", {"email": resident_user.email, "password": "wrong"}, format="json")
        other_ip = client_for().post(
            "/api/auth/login",
            {"email": resident_user_2.email, "password": PASSWORD},
            format="json",
            REMOTE_ADDR="198.51.100.7",
        )
        assert other_ip.status_code == status.HTTP_200_OK

    def test_client_cannot_choose_its_own_ip(self):
        """A forged X-Forwarded-For value must not change the IP the throttle counts."""
        request = RequestFactory().get(
            "/", HTTP_X_FORWARDED_FOR="203.0.113.9, 172.20.0.1", REMOTE_ADDR="172.20.0.5"
        )
        with override_settings(TRUSTED_PROXY_COUNT=0):
            assert get_client_ip(request) == "172.20.0.5"
        with override_settings(TRUSTED_PROXY_COUNT=1):
            assert get_client_ip(request) == "172.20.0.1"

    def test_unknown_email_still_hashes_the_password(self, monkeypatch):
        """AC-01.2: response time must not reveal whether an account exists."""
        calls = []
        monkeypatch.setattr(User, "set_password", lambda self, raw: calls.append(raw))
        client_for().post("/api/auth/login", {"email": "nobody@example.test", "password": "wrong"}, format="json")
        assert calls == ["wrong"]

    def test_login_requires_a_csrf_token(self, resident_user):
        """NFR-02: state-changing requests require a CSRF token."""
        client = APIClient(enforce_csrf_checks=True, raise_request_exception=False)
        response = client.post("/api/auth/login", {"email": resident_user.email, "password": PASSWORD}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        token = client.get("/api/auth/csrf").json()["csrfToken"]
        response = client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert response.status_code == status.HTTP_200_OK

    def test_lockout_helpers_stay_removed(self):
        assert not hasattr(AuthService, "calculate_lockout_duration")


@pytest.mark.django_db
class TestWardenReports:
    """A Warden may report for a Resident who cannot reach their account, and may do nothing else."""

    def test_warden_answers_clarification_on_their_own_report(
        self, warden_user, supervisor_user, location, category
    ):
        warden = client_for(warden_user)
        created = warden.post(
            "/api/requests/",
            {"location_id": location.id, "category_id": category.id, "description": "Reported for a student."},
            format="json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        assert created.json()["is_owner"] is True

        asked = client_for(supervisor_user).post(
            f"/api/requests/{created.json()['id']}/transition/",
            {"action": "REQUEST_CLARIFICATION", "expected_status": "SUBMITTED", "note": "Which tap is it exactly?"},
            format="json",
        )
        assert asked.status_code == status.HTTP_200_OK

        waiting = warden.get("/api/requests/?status=NEEDS_CLARIFICATION&mine=true").json()
        assert [item["id"] for item in waiting["results"]] == [created.json()["id"]]

        answered = warden.post(
            f"/api/requests/{created.json()['id']}/transition/",
            {"action": "PROVIDE_CLARIFICATION", "expected_status": "NEEDS_CLARIFICATION", "note": "Left basin tap."},
            format="json",
        )
        assert answered.status_code == status.HTTP_200_OK
        assert answered.json()["status"] == RequestStatus.SUBMITTED

    def test_warden_cannot_answer_for_another_persons_report(self, warden_user, resident_user, location, category):
        req = make_request(resident_user, location, category, RequestStatus.NEEDS_CLARIFICATION)
        response = client_for(warden_user).post(
            f"/api/requests/{req.id}/transition/",
            {"action": "PROVIDE_CLARIFICATION", "expected_status": "NEEDS_CLARIFICATION", "note": "Not my report."},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("action", ["APPROVE", "REJECT", "ASSIGN", "REASSIGN", "VERIFY_CLOSE", "REOPEN"])
    def test_warden_gets_403_in_every_state(self, warden_user, resident_user, location, category, action):
        """AC-16.1 and NFR-01: a forbidden role gets 403, never a 409 that reveals the state."""
        req = make_request(resident_user, location, category, RequestStatus.VERIFIED_CLOSED, Priority.LOW, closed=True)
        response = client_for(warden_user).post(
            f"/api/requests/{req.id}/transition/",
            {"action": action, "expected_status": "SUBMITTED", "note": "Trying to act on this."},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestRolesAndQueues:
    def test_wrong_role_gets_403_from_any_state(self, resident_user, location, category):
        req = make_request(resident_user, location, category)
        response = client_for(resident_user).post(
            f"/api/requests/{req.id}/transition/",
            {"action": "VERIFY_CLOSE", "expected_status": "SUBMITTED"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_has_no_maintenance_oversight_endpoints(self, admin_user, supervisor_user, warden_user):
        """Report 6.3: dashboard is Warden and Supervisor; technician list is Supervisor."""
        admin = client_for(admin_user)
        assert admin.get("/api/dashboard/").status_code == status.HTTP_403_FORBIDDEN
        assert admin.get("/api/technicians/").status_code == status.HTTP_403_FORBIDDEN
        assert client_for(warden_user).get("/api/technicians/").status_code == status.HTTP_403_FORBIDDEN
        assert client_for(supervisor_user).get("/api/technicians/").status_code == status.HTTP_200_OK

    def test_triage_queue_is_oldest_first_and_capped_at_50(self, supervisor_user, resident_user, location, category):
        """FR-08, TC-16."""
        created = [make_request(resident_user, location, category).id for _ in range(55)]
        client = client_for(supervisor_user)

        first = client.get("/api/triage-queue/").json()
        assert [item["id"] for item in first["results"]] == created[:50]
        assert first["total_count"] == 55
        assert first["status_totals"]["SUBMITTED"] == 55

        second = client.get("/api/triage-queue/?offset=50").json()
        assert [item["id"] for item in second["results"]] == created[50:]

        assert len(client.get("/api/triage-queue/?limit=500").json()["results"]) == 50
        assert client_for(resident_user).get("/api/triage-queue/").status_code == status.HTTP_403_FORBIDDEN

    def test_triage_queue_filters_by_residence_and_category(
        self, supervisor_user, resident_user, location, category, category_electrical, other_res_location
    ):
        wanted = make_request(resident_user, location, category)
        make_request(resident_user, location, category_electrical)
        other_resident = User.objects.create_user(
            email="other.resident@example.test",
            full_name="Other Resident",
            role=Role.RESIDENT,
            password=PASSWORD,
            residence=other_res_location.residence,
            student_number="OTHER001",
        )
        make_request(other_resident, other_res_location, category)

        results = client_for(supervisor_user).get(
            f"/api/triage-queue/?residence_id={location.residence_id}&category_id={category.id}"
        ).json()["results"]
        assert [item["id"] for item in results] == [wanted.id]

    def test_list_query_count_does_not_grow_with_rows(self, supervisor_user, resident_user, location, category):
        """NFR-06: no query per row."""
        client = client_for(supervisor_user)
        make_request(resident_user, location, category)
        with CaptureQueriesContext(connection) as small:
            client.get("/api/requests/")
        for _ in range(30):
            make_request(resident_user, location, category)
        with CaptureQueriesContext(connection) as large:
            client.get("/api/requests/")
        assert len(large) == len(small)

    def test_work_queue_hides_completed_work_and_orders_by_assignment(
        self, technician_user, supervisor_user, resident_user, location, category
    ):
        """AC-15.1 and FR-13."""
        def assign(request_status):
            req = make_request(resident_user, location, category, request_status, Priority.HIGH)
            WorkOrder.objects.create(request=req, technician=technician_user, assigned_by=supervisor_user)
            return req.id

        reported_first = make_request(resident_user, location, category, RequestStatus.ASSIGNED, Priority.HIGH)
        assigned_first = assign(RequestStatus.ASSIGNED)
        WorkOrder.objects.create(request=reported_first, technician=technician_user, assigned_by=supervisor_user)
        finished = assign(RequestStatus.WORK_COMPLETED)

        client = client_for(technician_user)
        queue = client.get("/api/work-queue/").json()
        assert [item["id"] for item in queue["results"]] == [assigned_first, reported_first.id]
        assert queue["status_totals"]["WORK_COMPLETED"] == 1

        completed = client.get("/api/work-queue/?status=WORK_COMPLETED").json()["results"]
        assert [item["id"] for item in completed] == [finished]

    def test_staff_email_is_supervisor_and_admin_only(
        self, resident_user, warden_user, supervisor_user, technician_user, location, category
    ):
        req = make_request(resident_user, location, category, RequestStatus.ASSIGNED, Priority.LOW)
        WorkOrder.objects.create(request=req, technician=technician_user, assigned_by=supervisor_user)
        url = f"/api/requests/{req.id}/"

        assert technician_user.email not in json.dumps(client_for(resident_user).get(url).json())
        assert technician_user.email not in json.dumps(client_for(warden_user).get(url).json())
        assert technician_user.email in json.dumps(client_for(supervisor_user).get(url).json())


@pytest.mark.django_db
class TestInputHandling:
    @pytest.mark.parametrize(
        "url",
        [
            "/api/requests/?category_id=abc",
            "/api/requests/?location_id=1%27%20OR%20%271%27=%271",
            "/api/requests/?residence_id=x",
            "/api/requests/?category_id=%C2%B2",
            "/api/requests/?limit=abc&offset=-1",
            "/api/triage-queue/?category_id=abc",
            "/api/locations/?residence_id=abc",
            "/api/dashboard/?residence_id=abc",
        ],
    )
    def test_bad_filter_values_are_ignored(self, supervisor_user, url):
        """ST-01: hostile filter values cause no error."""
        assert client_for(supervisor_user).get(url).status_code == status.HTTP_200_OK

    def test_st02_script_markup_is_stored_literally(self, resident_user, location, category, supervisor_user):
        """ST-02: the API returns markup unchanged as data; React renders it as text (see e2e)."""
        description = "<script>alert('stored')</script> tap is broken"
        created = client_for(resident_user).post(
            "/api/requests/",
            {"location_id": location.id, "category_id": category.id, "description": description},
            format="json",
        )
        assert created.status_code == status.HTTP_201_CREATED
        detail = client_for(supervisor_user).get(f"/api/requests/{created.json()['id']}/").json()
        assert detail["description"] == description

    def test_search_cannot_match_resident_identity_for_wardens(self, warden_user, resident_user, location, category):
        """BR-04: a search must not confirm who reported a fault."""
        make_request(resident_user, location, category)
        response = client_for(warden_user).get(f"/api/requests/?search={resident_user.full_name}")
        assert response.json()["results"] == []

    def test_audit_search_page_size_is_capped(self, admin_user):
        assert client_for(admin_user).get("/api/audit-logs/?limit=200").json()["limit"] == 50

    def test_users_are_paginated(self, admin_user):
        data = client_for(admin_user).get("/api/users/").json()
        assert data["limit"] == 50
        assert data["total_count"] == 1


@pytest.mark.django_db
class TestUserAdministration:
    def test_refused_update_leaves_no_trace(self, admin_user, technician_user):
        """FR-17: an audit event is written with the change itself, or not at all."""
        target = client_for(technician_user)
        response = client_for(admin_user).patch(
            f"/api/users/{technician_user.id}/",
            {"is_active": False, "role": "RESIDENT"},
            format="json",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        technician_user.refresh_from_db()
        assert technician_user.is_active is True
        assert not AuditEvent.objects.filter(target_user=technician_user).exists()
        assert target.get("/api/me").status_code == status.HTTP_200_OK

    def test_edit_saves_residence_and_student_number(self, admin_user, resident_user, other_residence):
        """FR-03."""
        response = client_for(admin_user).patch(
            f"/api/users/{resident_user.id}/",
            {"residence_id": other_residence.id, "student_number": "NEW999"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        resident_user.refresh_from_db()
        assert resident_user.residence_id == other_residence.id
        assert resident_user.student_number == "NEW999"
        # The old room is in the old residence
        assert resident_user.assigned_location_id is None

    def test_duplicate_student_number_is_a_field_error(self, admin_user, resident_user, resident_user_2):
        response = client_for(admin_user).patch(
            f"/api/users/{resident_user.id}/",
            {"student_number": resident_user_2.student_number},
            format="json",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.django_db
class TestCsvImport:
    def test_short_row_is_reported_not_a_crash(self, admin_user, residence):
        response = upload(client_for(admin_user), b"email,full_name,student_number\na@example.test,Only Two\n")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()["fields"]["bad_rows"][0]["row"] == 2

    def test_role_residence_and_room_columns_are_honoured(self, admin_user, residence, other_residence, location):
        """FR-04 names these columns."""
        content = (
            "email,full_name,role,residence,student_number,room\n"
            f"res@example.test,New Resident,RESIDENT,{residence.name},S100,{location.label}\n"
            f"ward@example.test,New Warden,WARDEN,{other_residence.name},,\n"
            "tech@example.test,New Technician,TECHNICIAN,,,\n"
            "plain@example.test,Plain Resident,,,S101,\n"
        ).encode()
        response = upload(client_for(admin_user), content)
        assert response.status_code == status.HTTP_201_CREATED

        resident = User.objects.get(email="res@example.test")
        assert (resident.role, resident.assigned_location_id) == (Role.RESIDENT, location.id)
        warden = User.objects.get(email="ward@example.test")
        assert (warden.role, warden.residence_id) == (Role.WARDEN, other_residence.id)
        assert User.objects.get(email="tech@example.test").role == Role.TECHNICIAN
        assert User.objects.get(email="plain@example.test").role == Role.RESIDENT

    def test_bad_role_residence_and_room_reject_the_whole_file(self, admin_user, residence):
        content = (
            "email,full_name,role,residence,student_number,room\n"
            "good@example.test,Good Row,RESIDENT,,S200,\n"
            "a@example.test,Bad Role,PRESIDENT,,S201,\n"
            "b@example.test,Bad Residence,RESIDENT,Nowhere Hall,S202,\n"
            f"c@example.test,Bad Room,RESIDENT,{residence.name},S203,Z.999\n"
        ).encode()
        response = upload(client_for(admin_user), content)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert [item["row"] for item in response.json()["fields"]["bad_rows"]] == [3, 4, 5]
        assert not User.objects.filter(email="good@example.test").exists()

    def test_existing_email_is_compared_case_insensitively(self, admin_user, residence):
        """AC-04.2."""
        User.objects.create_user(
            email="Mixed.Case@example.test", full_name="Existing", role=Role.TECHNICIAN, password=PASSWORD
        )
        response = upload(
            client_for(admin_user),
            b"email,full_name,student_number\nmixed.case@example.test,New Person,S300\n",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.django_db(transaction=True)
class TestConcurrency:
    def test_simultaneous_submits_with_one_token_create_one_request(self, resident_user, location, category):
        """AC-05.3: a double tap is never a server error."""
        token = str(uuid.uuid4())
        user_id = resident_user.id

        def submit(_):
            response = client_for(User.objects.get(id=user_id)).post(
                "/api/requests/",
                {
                    "location_id": location.id,
                    "category_id": category.id,
                    "description": "Double tapped submit button here.",
                    "client_token": token,
                },
                format="json",
            )
            connection.close()
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(8) as executor:
            codes = list(executor.map(submit, range(8)))

        assert set(codes) <= {status.HTTP_200_OK, status.HTTP_201_CREATED}
        assert codes.count(status.HTTP_201_CREATED) == 1
        assert MaintenanceRequest.objects.filter(client_token=token).count() == 1

    def test_deactivation_and_assignment_cannot_cross(
        self, admin_user, supervisor_user, technician_user, resident_user, location, category
    ):
        """ADR-02, BR-07, INV-3: an inactive Technician never holds an active work order."""
        technician_id = technician_user.id

        for _ in range(25):
            User.objects.filter(id=technician_id).update(is_active=True)
            req = make_request(resident_user, location, category, RequestStatus.APPROVED, Priority.LOW)

            def assign():
                client_for(User.objects.get(id=supervisor_user.id)).post(
                    f"/api/requests/{req.id}/transition/",
                    {"action": "ASSIGN", "expected_status": "APPROVED", "technician_id": technician_id},
                    format="json",
                )
                connection.close()

            def deactivate():
                client_for(User.objects.get(id=admin_user.id)).patch(
                    f"/api/users/{technician_id}/", {"is_active": False}, format="json"
                )
                connection.close()

            with concurrent.futures.ThreadPoolExecutor(2) as executor:
                futures = [executor.submit(assign), executor.submit(deactivate)]
                for future in futures:
                    future.result()

            technician = User.objects.get(id=technician_id)
            active = WorkOrder.objects.filter(technician=technician, ended_at__isnull=True)
            assert technician.is_active or not active.exists()
            active.update(ended_at=timezone.now(), end_reason="COMPLETED")


@pytest.mark.django_db
class TestDatabaseControls:
    def test_statement_timeout_is_set(self):
        """Section 5.7: database statement timeout."""
        with connection.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            assert cursor.fetchone()[0] != "0"

    def test_seed_creates_documented_accounts_and_sample_requests(self):
        """Section 8: demo accounts match the README, and a fresh system has requests to show."""
        call_command("seed_data", with_demo=True, verbosity=0)
        for role in ("resident", "supervisor", "technician", "warden", "admin"):
            assert User.objects.filter(email=f"{role}@example.test").exists()

        statuses = set(MaintenanceRequest.objects.values_list("status", flat=True))
        assert {RequestStatus.SUBMITTED, RequestStatus.WORK_COMPLETED, RequestStatus.VERIFIED_CLOSED} <= statuses

        count = MaintenanceRequest.objects.count()
        call_command("seed_data", with_demo=True, verbosity=0)
        assert MaintenanceRequest.objects.count() == count
