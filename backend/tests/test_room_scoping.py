"""Test Suite for Student Room Assignment and Warden Scoping.

Verifies:
1. Residents can only submit maintenance requests for their assigned room and shared common areas.
2. Residents attempting to report faults on other students' rooms are rejected (422 Unprocessable Entity).
3. Residents without an assigned room can only submit for common areas.
4. Residence Wardens can submit maintenance requests for ALL rooms and common areas in their residence.
5. Wardens cannot submit requests for locations outside their assigned residence (422 Unprocessable Entity).
6. Location listing (/api/locations/) is scoped:
   - Residents only see their assigned room + common areas.
   - Wardens see all rooms and common areas in their residence.
   - Admins see all locations.
7. Admin user management API enforces room assignment rules (residents only).
"""

import uuid

import pytest
from apps.accounts.models import User
from apps.locations.models import FaultCategory, Location
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestRoomAssignmentAndScoping:
    """Room scoping and role-based request submission permission tests."""

    def test_resident_submits_for_assigned_room_success(
        self,
        resident_client: APIClient,
        resident_user: User,
        category: FaultCategory,
    ):
        """Resident can successfully submit a maintenance request for their assigned room."""
        assert resident_user.assigned_location is not None

        resp = resident_client.post(
            "/api/requests/",
            {
                "location_id": resident_user.assigned_location.id,
                "category_id": category.id,
                "description": "The study lamp socket in my room is loose.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["location"]["id"] == resident_user.assigned_location.id
        assert data["resident"]["id"] == resident_user.id

    def test_resident_submits_for_common_area_success(
        self,
        resident_client: APIClient,
        resident_user: User,
        common_area_location: Location,
        category: FaultCategory,
    ):
        """Resident can successfully submit a maintenance request for a common area."""
        resp = resident_client.post(
            "/api/requests/",
            {
                "location_id": common_area_location.id,
                "category_id": category.id,
                "description": "The common study room window latch is jammed.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["location"]["id"] == common_area_location.id

    def test_resident_cannot_submit_for_another_room(
        self,
        resident_client: APIClient,
        resident_user: User,
        location_b: Location,
        category: FaultCategory,
    ):
        """Resident is strictly blocked from submitting a request for another student's room."""
        assert resident_user.assigned_location.id != location_b.id

        resp = resident_client.post(
            "/api/requests/",
            {
                "location_id": location_b.id,
                "category_id": category.id,
                "description": "Attempting to file a ticket on someone else's room.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        error_detail = str(resp.json())
        assert "Residents can only submit requests for their assigned room or common areas." in error_detail

    def test_resident_without_assigned_room_can_only_report_common_areas(
        self,
        resident_user: User,
        location: Location,
        common_area_location: Location,
        category: FaultCategory,
    ):
        """Resident with unassigned room can report common areas but not private rooms."""
        resident_user.assigned_location = None
        resident_user.save()

        client = APIClient()
        client.force_login(resident_user)

        # Attempt private room -> Rejected with 422
        resp_room = client.post(
            "/api/requests/",
            {
                "location_id": location.id,
                "category_id": category.id,
                "description": "Reporting room fault with no assigned room.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp_room.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Residents can only submit requests for their assigned room or common areas." in str(resp_room.json())

        # Common area -> Allowed (201 Created)
        resp_ca = client.post(
            "/api/requests/",
            {
                "location_id": common_area_location.id,
                "category_id": category.id,
                "description": "Reporting study room light out.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp_ca.status_code == status.HTTP_201_CREATED

    def test_warden_can_submit_for_any_room_in_residence(
        self,
        warden_client: APIClient,
        warden_user: User,
        location: Location,
        location_b: Location,
        category: FaultCategory,
    ):
        """Warden can submit requests for any room in their residence."""
        resp1 = warden_client.post(
            "/api/requests/",
            {
                "location_id": location.id,
                "category_id": category.id,
                "description": "Warden inspection noted leaking radiator in Room 101.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp1.status_code == status.HTTP_201_CREATED

        resp2 = warden_client.post(
            "/api/requests/",
            {
                "location_id": location_b.id,
                "category_id": category.id,
                "description": "Warden inspection noted broken wardrobe in Room 205.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp2.status_code == status.HTTP_201_CREATED

    def test_warden_can_submit_for_common_area(
        self,
        warden_client: APIClient,
        common_area_location: Location,
        category: FaultCategory,
    ):
        """Warden can submit requests for common areas in their residence."""
        resp = warden_client.post(
            "/api/requests/",
            {
                "location_id": common_area_location.id,
                "category_id": category.id,
                "description": "Warden reporting damaged front door lock in common area.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_warden_cannot_submit_for_other_residence(
        self,
        warden_client: APIClient,
        other_res_location: Location,
        category: FaultCategory,
    ):
        """Warden cannot submit requests for locations belonging to another residence."""
        resp = warden_client.post(
            "/api/requests/",
            {
                "location_id": other_res_location.id,
                "category_id": category.id,
                "description": "Warden attempting to report fault in another residence.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        error_detail = str(resp.json())
        assert "Location must be within your assigned residence." in error_detail

    def test_location_list_scoping_resident_vs_warden(
        self,
        resident_client: APIClient,
        resident_user: User,
        warden_client: APIClient,
        admin_client: APIClient,
        location: Location,
        location_b: Location,
        common_area_location: Location,
        other_res_location: Location,
    ):
        """Verify /api/locations/ queryset scoping for Resident, Warden, and Admin."""
        # Resident sees assigned room + common area in residence; does NOT see location_b or other_res_location
        res_resp = resident_client.get("/api/locations/")
        assert res_resp.status_code == status.HTTP_200_OK
        res_loc_ids = [item["id"] for item in res_resp.json()]
        assert location.id in res_loc_ids
        assert common_area_location.id in res_loc_ids
        assert location_b.id not in res_loc_ids
        assert other_res_location.id not in res_loc_ids

        # Warden sees all locations in Moroka Hall; does NOT see other_res_location
        warden_resp = warden_client.get("/api/locations/")
        assert warden_resp.status_code == status.HTTP_200_OK
        warden_loc_ids = [item["id"] for item in warden_resp.json()]
        assert location.id in warden_loc_ids
        assert location_b.id in warden_loc_ids
        assert common_area_location.id in warden_loc_ids
        assert other_res_location.id not in warden_loc_ids

        # Admin sees all locations
        admin_resp = admin_client.get("/api/locations/")
        assert admin_resp.status_code == status.HTTP_200_OK
        admin_loc_ids = [item["id"] for item in admin_resp.json()]
        assert location.id in admin_loc_ids
        assert location_b.id in admin_loc_ids
        assert common_area_location.id in admin_loc_ids
        assert other_res_location.id in admin_loc_ids

    def test_admin_assign_and_change_resident_room(
        self,
        admin_client: APIClient,
        resident_user: User,
        location_b: Location,
    ):
        """Admin can reassign a resident's room via User Admin API."""
        resp = admin_client.patch(
            f"/api/users/{resident_user.id}/",
            {"assigned_location_id": location_b.id},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["assigned_location"] == location_b.id
        assert data["assigned_location_name"] == f"Block {location_b.block} Fl {location_b.floor} ({location_b.label})"

        resident_user.refresh_from_db()
        assert resident_user.assigned_location_id == location_b.id

    def test_admin_cannot_assign_room_to_technician(
        self,
        admin_client: APIClient,
        technician_user: User,
        location: Location,
    ):
        """Admin cannot assign a room to non-resident roles."""
        resp = admin_client.patch(
            f"/api/users/{technician_user.id}/",
            {"assigned_location_id": location.id},
            format="json",
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Assigned location can only be set for residents." in str(resp.json())

    def test_resident_can_submit_for_laundry_room_common_area(
        self,
        resident_client: APIClient,
        resident_user: User,
        category: FaultCategory,
    ):
        """Resident can successfully report maintenance faults for the shared laundry room."""
        from apps.locations.models import LocationKind

        laundry_room = Location.objects.create(
            residence=resident_user.residence,
            block="B",
            floor=1,
            label="Laundry Room",
            kind=LocationKind.COMMON_AREA,
            is_active=True,
        )

        resp = resident_client.post(
            "/api/requests/",
            {
                "location_id": laundry_room.id,
                "category_id": category.id,
                "description": "Washing machine #3 is leaking water onto the laundry room floor.",
                "client_token": str(uuid.uuid4()),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["location"]["id"] == laundry_room.id
        assert data["location"]["label"] == "Laundry Room"
        assert data["location"]["kind"] == "COMMON_AREA"

