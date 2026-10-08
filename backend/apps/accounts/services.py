from config.exceptions import ThrottledException, UnauthenticatedException, ValidationException
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import AuditService


def get_client_ip(request: HttpRequest) -> str:
    """Extract client IP address handling reverse proxy X-Forwarded-For headers."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


class AuthService:
    """Handles authentication, session rotation, password policy, and login throttling."""

    MAX_FAILED_ATTEMPTS = 5
    THROTTLE_WINDOW_SECONDS = 60

    @classmethod
    def authenticate(
        cls,
        *,
        email: str,
        password: str,
        request: HttpRequest,
    ) -> User:
        """Authenticate user by email and password, enforcing sliding window throttling."""
        normalized_email = email.strip().lower()
        ip_address = get_client_ip(request)

        # 1. Check sliding window throttle (Section 4.4, NFR-02)
        failed_count = AuditService.count_failed_logins(
            email=normalized_email,
            ip_address=ip_address,
            window_seconds=cls.THROTTLE_WINDOW_SECONDS,
        )
        if failed_count >= cls.MAX_FAILED_ATTEMPTS:
            raise ThrottledException("Too many failed login attempts. Please try again in a minute.")

        # 2. Look up user
        user = User.objects.filter(email__iexact=normalized_email).first()

        # Generic error message per NFR-02 to prevent account enumeration
        generic_error = "Invalid email or password."

        if user is None or not user.check_password(password):
            AuditService.record(
                action=AuditAction.LOGIN_FAILED,
                target_user=user,
                details={
                    "email": normalized_email,
                    "ip_address": ip_address,
                    "reason": "invalid_credentials",
                },
            )
            raise UnauthenticatedException(generic_error)

        # 3. Check active status (BR-07)
        if not user.is_active:
            AuditService.record(
                action=AuditAction.LOGIN_FAILED,
                actor=user,
                target_user=user,
                details={
                    "email": normalized_email,
                    "ip_address": ip_address,
                    "reason": "account_deactivated",
                },
            )
            raise UnauthenticatedException(generic_error)

        # 4. Successful login: update last_login and cycle session (ADR-03)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        # Cycle session to prevent session fixation and attach authenticated user
        django_login(request, user)

        return user

    @classmethod
    def logout(cls, request: HttpRequest) -> None:
        """Terminate the current user session and flush cookies."""
        django_logout(request)

    @classmethod
    def change_password(
        cls,
        *,
        user: User,
        current_password: str | None,
        new_password: str,
        request: HttpRequest | None = None,
    ) -> None:
        """Validate and apply a password change with Argon2id hashing (FR-02)."""
        # If password change is forced by temp password, current_password can be optional if already validated
        if user.must_change_password:
            if current_password and not user.check_password(current_password):
                raise ValidationException(
                    "Current temporary password is incorrect.",
                    fields={"current_password": ["Incorrect temporary password."]},
                )
        else:
            if not current_password or not user.check_password(current_password):
                raise ValidationException(
                    "Current password is incorrect.",
                    fields={"current_password": ["Incorrect password."]},
                )

        # Length validation (>= 10 chars per Section 2 / Security)
        if len(new_password) < 10:
            raise ValidationException(
                "Password must be at least 10 characters long.",
                fields={"new_password": ["Password must be at least 10 characters long."]},
            )

        # Django built-in validators check
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise ValidationException(
                "Password does not meet complexity requirements.",
                fields={"new_password": list(exc.messages)},
            ) from exc

        # Update password hash and clear mandatory change flag
        was_forced = user.must_change_password
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        if request is not None:
            update_session_auth_hash(request, user)

        # Audit event
        AuditService.record(
            action=AuditAction.PASSWORD_CHANGED,
            actor=user,
            target_user=user,
            details={"forced": was_forced},
        )
