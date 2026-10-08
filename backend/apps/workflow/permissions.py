"""PermissionPolicy defining role-based query scopes and object access (BR-04, BR-05, Section 5.4)."""

from django.db.models import QuerySet

from apps.accounts.models import Role, User
from apps.workflow.models import MaintenanceRequest


class PermissionPolicy:
    """Central authority for role-based object authorization and queryset filtering."""

    @staticmethod
    def scope_requests(user: User) -> QuerySet[MaintenanceRequest]:
        """Return requests visible to the given user based on role and residence scope (BR-05)."""
        base_qs = (
            MaintenanceRequest.objects.select_related("resident", "location", "category", "location__residence")
            .all()
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
            # Technicians will see requests linked to their active work orders (Slice 5)
            # Prior to Slice 4/5, technician queue is empty
            return base_qs.none()

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
            return False

        return False
