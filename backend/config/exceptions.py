"""Standardized API exception handling conforming to project specification (Section 4.7, 6.3)."""

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class AppException(Exception):
    """Base application exception with standardized code and status."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"
    default_message: str = "An error occurred."

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        *,
        fields: dict[str, Any] | None = None,
        current_status: str | None = None,
    ):
        self.message = message or self.default_message
        if code:
            self.code = code
        self.fields = fields
        self.current_status = current_status
        super().__init__(self.message)


class UnauthenticatedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHENTICATED"
    default_message = "Authentication required or session ended."


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    default_message = "You do not have permission to perform this action."


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    default_message = "Requested resource not found or outside your scope."


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    default_message = "State conflict detected."


class ValidationException(AppException):
    status_code = 422
    code = "VALIDATION_ERROR"
    default_message = "Validation failure."


class ThrottledException(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "THROTTLED"
    default_message = "Too many requests. Please try again later."


def standard_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Format all API exceptions into:

    {
        "code": "...",
        "message": "...",
        "fields": {...},          # when applicable
        "current_status": "..."   # when applicable
    }
    """
    if isinstance(exc, AppException):
        payload: dict[str, Any] = {
            "code": exc.code,
            "message": exc.message,
        }
        if exc.fields:
            payload["fields"] = exc.fields
        if exc.current_status:
            payload["current_status"] = exc.current_status
        return Response(payload, status=exc.status_code)

    # A database constraint caught what the services did not, such as a duplicate insert
    # that lost a race. The change was refused, so report a conflict (Table 5.8).
    if isinstance(exc, IntegrityError):
        return Response(
            {"code": "CONFLICT", "message": "This change conflicts with another change. Please refresh and try again."},
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        return Response(
            {
                "code": "UNAUTHENTICATED",
                "message": "Authentication required or session expired.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Let DRF handle standard REST exceptions
    response = exception_handler(exc, context)

    if response is not None:
        code = "ERROR"
        message = "An error occurred."
        fields = None
        current_status = None

        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            code = "UNAUTHENTICATED"
            message = "Authentication required or session expired."
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            code = "FORBIDDEN"
            message = "You do not have permission to access this resource."
        elif response.status_code == status.HTTP_404_NOT_FOUND:
            code = "NOT_FOUND"
            message = "Requested resource was not found."
        elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            code = "THROTTLED"
            message = "Too many requests. Please try again later."
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            # Map DRF validation errors to HTTP 422 per Section 6.2
            response.status_code = 422
            code = "VALIDATION_ERROR"
            message = "Validation failure."
            if isinstance(response.data, dict):
                fields = response.data
            elif isinstance(response.data, list):
                fields = {"detail": response.data}

        payload = {
            "code": code,
            "message": message,
        }
        if fields:
            payload["fields"] = fields
        if current_status:
            payload["current_status"] = current_status

        response.data = payload
        return response

    if isinstance(exc, Http404):
        return Response(
            {"code": "NOT_FOUND", "message": "Requested resource was not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, DjangoPermissionDenied):
        return Response(
            {"code": "FORBIDDEN", "message": "You do not have permission to perform this action."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return None
