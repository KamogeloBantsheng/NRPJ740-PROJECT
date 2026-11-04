"""Permissions & Scoping Security Test Suite (Phase 10: TC-14, TC-16, TC-28, TC-36, NT-01, ST-03, ST-04, ST-06).

Verifies strict object-level authorization, role-based queryset scoping (BR-04, BR-05),
resident identity masking for Warden/Technician, mass assignment immunity, and the NT-01 security matrix.
"""

import pytest
from apps.accounts.models import Role, User
from apps.locations.models import FaultCategory, Location, Residence
from apps.workflow.models import MaintenanceRequest, Priority, RequestStatus, WorkOrder
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestPermissionsAndSecurity:
    """Covers TC-14, TC-16, TC-28, TC-36, NT-01, ST-03, ST-04, ST-06."""

    def test_tc14_and_st04_resident_scoped_to_own_requests(
        self,
        resident_client: APIClient,
        resident_user: User,
        supervisor_user: User,
        residence: Residence,
        location: Location,
        category: FaultCategory,
    ):
        """TC-14 & ST-04: Resident reads own requests only; querying another resident's request returns 404 (BR-05)."""
        # Create second resident in same residence
        other_resident = User.objects.create_user(
            email="other.resident@spu.ac.za",
            full_name="Other Resident",
            role=Role.RESIDENT,
            student_number="202399999",
            residence=residence,
            password="StrongPassword123!",
        )

        req_own = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Leaking kitchen sink pipe in my unit.",
            status=RequestStatus.SUBMITTED,
        )
        req_other = MaintenanceRequest.objects.create(
            resident=other_resident,
            location=location,
            category=category,
            description="Broken window latch in other unit.",
            status=RequestStatus.SUBMITTED,
        )

        # 1. Listing endpoint: Resident sees strictly own requests
        list_resp = resident_client.get("/api/requests/")
        assert list_resp.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in list_resp.json()["results"]]
        assert req_own.id in ids
        assert req_other.id not in ids

        # 2. Detail endpoint: Accessing other resident's request returns 404 Not Found (ST-04)
        detail_resp = resident_client.get(f"/api/requests/{req_other.id}/")
        assert detail_resp.status_code == status.HTTP_404_NOT_FOUND

        # Own request returns 200 OK
        own_resp = resident_client.get(f"/api/requests/{req_own.id}/")
        assert own_resp.status_code == status.HTTP_200_OK

    def test_tc16_supervisor_triage_queue_filtering(
        self,
        supervisor_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-16: Supervisor triage queue orders and filters by status within assigned residence (SCR-03)."""
        req_sub = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Light switch sparks when flipped.",
            status=RequestStatus.SUBMITTED,
        )
        req_app = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Door handle fell off internal door.",
            status=RequestStatus.APPROVED,
            priority=Priority.LOW,
        )

        # Filter by status=SUBMITTED
        resp_filtered = supervisor_client.get("/api/requests/?status=SUBMITTED")
        assert resp_filtered.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in resp_filtered.json()["results"]]
        assert req_sub.id in ids
        assert req_app.id not in ids

    def test_tc28_and_st06_technician_work_queue_and_privacy(
        self,
        technician_client: APIClient,
        technician_user: User,
        technician_user_2: User,
        resident_user: User,
        supervisor_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-28 & ST-06: Technician sees assigned work orders only; resident identity stripped (BR-04, Table 5.2)."""
        req1 = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Toilet cistern filling valve broken.",
            status=RequestStatus.ASSIGNED,
            priority=Priority.HIGH,
        )
        WorkOrder.objects.create(
            request=req1,
            technician=technician_user,
            assigned_by=supervisor_user,
        )

        req2 = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Blocked shower drain in corridor.",
            status=RequestStatus.ASSIGNED,
            priority=Priority.MEDIUM,
        )
        WorkOrder.objects.create(
            request=req2,
            technician=technician_user_2,
            assigned_by=supervisor_user,
        )

        # 1. Work queue lists only requests assigned to this technician
        queue_resp = technician_client.get("/api/work-queue/")
        assert queue_resp.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in queue_resp.json()["results"]]
        assert req1.id in ids
        assert req2.id not in ids

        # 2. Detail view: Accessing unassigned request returns 404 (ST-06)
        unassigned_resp = technician_client.get(f"/api/requests/{req2.id}/")
        assert unassigned_resp.status_code == status.HTTP_404_NOT_FOUND

        # 3. Privacy: Accessing assigned request strips resident personal identity
        assigned_resp = technician_client.get(f"/api/requests/{req1.id}/")
        assert assigned_resp.status_code == status.HTTP_200_OK
        detail_data = assigned_resp.json()
        assert detail_data["resident"] is None

    def test_tc36_warden_dashboard_and_read_only(
        self,
        warden_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """TC-36: Warden dashboard scoped to own residence; resident identity stripped; mutations return 403."""
        req = MaintenanceRequest.objects.create(
            resident=resident_user,
            location=location,
            category=category,
            description="Cracked window pane in lounge area.",
            status=RequestStatus.SUBMITTED,
        )

        # 1. Dashboard access returns 200 and reflects own residence scope
        dash_resp = warden_client.get("/api/dashboard/")
        assert dash_resp.status_code == status.HTTP_200_OK
        metrics = dash_resp.json()
        assert "status_counts" in metrics
        assert metrics["scope"]["residence_name"] == "Moroka Hall of Residence"

        # 2. Detail view: Resident personal identity stripped for Warden
        req_resp = warden_client.get(f"/api/requests/{req.id}/")
        assert req_resp.status_code == status.HTTP_200_OK
        assert req_resp.json()["resident"] is None

        # 3. Dashboard is read-only: POST, PUT, DELETE return 403
        assert warden_client.post("/api/dashboard/").status_code == status.HTTP_403_FORBIDDEN
        assert warden_client.put("/api/dashboard/").status_code == status.HTTP_403_FORBIDDEN
        assert warden_client.delete("/api/dashboard/").status_code == status.HTTP_403_FORBIDDEN

    def test_st03_mass_assignment_protection(
        self,
        resident_client: APIClient,
        resident_user: User,
        location: Location,
        category: FaultCategory,
    ):
        """ST-03: Resident cannot inject status, priority, resident_id, or timestamps (Mass Assignment Protection)."""
        malicious_payload = {
            "location_id": location.id,
            "category_id": category.id,
            "description": "Legitimate maintenance description for tap leak.",
            "status": "APPROVED",
            "priority": "CRITICAL",
            "resident_id": 9999,
            "closed_at": "2020-01-01T00:00:00Z",
            "tracking_number": "MR-999999",
        }

        resp = resident_client.post("/api/requests/", malicious_payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()

        # Verify status is defaulted to SUBMITTED and priority is None
        assert data["status"] == RequestStatus.SUBMITTED
        assert data["priority"] is None
        assert data["resident"]["id"] == resident_user.id
        assert data["tracking_number"] != "MR-999999"

        req = MaintenanceRequest.objects.get(id=data["id"])
        assert req.status == RequestStatus.SUBMITTED
        assert req.priority is None
        assert req.resident_id == resident_user.id
        assert req.closed_at is None

    def test_nt01_automated_role_endpoint_permission_matrix(
        self,
        admin_client: APIClient,
        supervisor_client: APIClient,
        warden_client: APIClient,
        technician_client: APIClient,
        resident_client: APIClient,
    ):
        """NT-01: Automated role-endpoint security matrix testing every privileged endpoint across all 5 roles."""
        # 1. Operational Dashboard (Admin, Supervisor, Warden allowed; Resident & Technician 403)
        assert admin_client.get("/api/dashboard/").status_code == status.HTTP_403_FORBIDDEN
        assert supervisor_client.get("/api/dashboard/").status_code == status.HTTP_200_OK
        assert warden_client.get("/api/dashboard/").status_code == status.HTTP_200_OK
        assert resident_client.get("/api/dashboard/").status_code == status.HTTP_403_FORBIDDEN
        assert technician_client.get("/api/dashboard/").status_code == status.HTTP_403_FORBIDDEN

        # 2. Technician Work Queue (Technician allowed; others 403)
        assert technician_client.get("/api/work-queue/").status_code == status.HTTP_200_OK
        assert resident_client.get("/api/work-queue/").status_code == status.HTTP_403_FORBIDDEN
        assert supervisor_client.get("/api/work-queue/").status_code == status.HTTP_403_FORBIDDEN
        assert warden_client.get("/api/work-queue/").status_code == status.HTTP_403_FORBIDDEN
        assert admin_client.get("/api/work-queue/").status_code == status.HTTP_403_FORBIDDEN

        # 3. Global Audit Logs (Admin allowed; others 403)
        assert admin_client.get("/api/audit-logs/").status_code == status.HTTP_200_OK
        assert supervisor_client.get("/api/audit-logs/").status_code == status.HTTP_403_FORBIDDEN
        assert warden_client.get("/api/audit-logs/").status_code == status.HTTP_403_FORBIDDEN
        assert technician_client.get("/api/audit-logs/").status_code == status.HTTP_403_FORBIDDEN
        assert resident_client.get("/api/audit-logs/").status_code == status.HTTP_403_FORBIDDEN

        # 4. User Administration (Admin allowed; others 403)
        assert admin_client.get("/api/users/").status_code == status.HTTP_200_OK
        assert supervisor_client.get("/api/users/").status_code == status.HTTP_403_FORBIDDEN
        assert warden_client.get("/api/users/").status_code == status.HTTP_403_FORBIDDEN
        assert technician_client.get("/api/users/").status_code == status.HTTP_403_FORBIDDEN
        assert resident_client.get("/api/users/").status_code == status.HTTP_403_FORBIDDEN
