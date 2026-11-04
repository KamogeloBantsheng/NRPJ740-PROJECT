"""Permission policies and role-based guards (BR-07, Section 5.7)."""

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.accounts.models import Role


class IsActiveUser(BasePermission):
    """Allows access only to authenticated and active users."""

    def has_permission(self, request: Request, view: Any) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_active)


class HasRole(BasePermission):
    """Allows access only to users possessing one of the allowed roles."""

    allowed_roles: tuple[str, ...] = ()

    def __init__(self, *roles: str):
        if roles:
            self.allowed_roles = roles

    def has_permission(self, request: Request, view: Any) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not user.is_active:
            return False
        return user.role in self.allowed_roles


class IsAdmin(HasRole):
    allowed_roles = (Role.ADMIN,)


class IsSupervisor(HasRole):
    allowed_roles = (Role.SUPERVISOR,)


class IsSupervisorOrAdmin(HasRole):
    allowed_roles = (Role.SUPERVISOR, Role.ADMIN)


class IsTechnician(HasRole):
    allowed_roles = (Role.TECHNICIAN,)


class IsResident(HasRole):
    allowed_roles = (Role.RESIDENT,)


class IsWarden(HasRole):
    allowed_roles = (Role.WARDEN,)
