"""PermissionPolicy defining role-based query scopes and object access (BR-04, BR-05, Section 5.4)."""

from django.db.models import Prefetch, QuerySet

from apps.accounts.models import Role, User
from apps.workflow.models import MaintenanceRequest, WorkOrder


class PermissionPolicy:
    """Central authority for role-based object authorization and queryset filtering."""

    @staticmethod
    def scope_requests(user: User) -> QuerySet[MaintenanceRequest]:
        """Return requests visible to the given user based on role and residence scope (BR-05)."""
        # The active work order is fetched in one extra query, not one per row (NFR-06)
        base_qs = MaintenanceRequest.objects.select_related(
            "resident", "location", "category", "location__residence"
        ).prefetch_related(
            Prefetch(
                "work_orders",
                queryset=WorkOrder.objects.filter(ended_at__isnull=True).select_related("technician"),
                to_attr="active_work_orders",
            )
        )

        if user.role == Role.RESIDENT:
            # Residents see strictly their own submitted requests
            return base_qs.filter(resident=user)

        if user.role in (Role.SUPERVISOR, Role.WARDEN):
            # Supervisors and Wardens see all requests within their assigned residence
            if user.residence_id:
                return base_qs.filter(location__residence_id=user.residence_id)
            return base_qs

        if user.role == Role.ADMIN:
            # Administrators see all requests across all residences
            return base_qs

        if user.role == Role.TECHNICIAN:
            # Technicians see requests linked to their active work orders (Slice 5, FR-13, BR-04)
            return base_qs.filter(
                work_orders__technician=user,
                work_orders__ended_at__isnull=True,
            ).distinct()

        return base_qs.none()

    @staticmethod
    def can_view_request(user: User, req: MaintenanceRequest) -> bool:
        """Determine whether user has permission to inspect the given request."""
        if user.role == Role.RESIDENT:
            return req.resident_id == user.id

        if user.role in (Role.SUPERVISOR, Role.WARDEN):
            if user.residence_id:
                return req.location.residence_id == user.residence_id
            return True

        if user.role == Role.ADMIN:
            return True

        if user.role == Role.TECHNICIAN:
            return req.work_orders.filter(
                technician=user,
                ended_at__isnull=True,
            ).exists()

        return False
