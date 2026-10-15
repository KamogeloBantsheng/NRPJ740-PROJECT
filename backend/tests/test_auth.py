"""Authentication & Security Test Suite (Phase 10: TC-01 to TC-05, NT-02, ST-05).

Verifies Argon2id password hashing, session lifecycle, brute-force throttling (BR-07, NFR-02),
forced password rotation on temporary credentials, and session invalidation on deactivation.
"""

import pytest
from apps.accounts.models import Role, User
from apps.audit.models import AuditAction, AuditEvent
from django.contrib.auth.hashers import identify_hasher
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestAuthentication:
    """Covers TC-01 to TC-05, NT-02, and ST-05."""

    def test_tc01_sign_in_valid_credentials(self, api_client: APIClient, resident_user: User):
        """TC-01: Valid sign-in creates session and returns user profile (FR-01, AC-01.1)."""
        response = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == resident_user.id
        assert data["email"] == resident_user.email
        assert data["role"] == Role.RESIDENT
        # Verify session cookie was set
        assert "sessionid" in response.cookies

    def test_tc02_generic_error_on_invalid_credentials(self, api_client: APIClient, resident_user: User):
        """TC-02: Wrong password or unknown email returns identical 401 message (FR-01, AC-01.2)."""
        # Wrong password
        resp_wrong_pwd = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "WrongPassword#999"},
            format="json",
        )
        assert resp_wrong_pwd.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp_wrong_pwd.json()["message"] == "Invalid email or password."

        # Unknown email
        resp_unknown_email = api_client.post(
            "/api/auth/login",
            {"email": "nonexistent.user@spu.ac.za", "password": "AnyPassword#123"},
            format="json",
        )
        assert resp_unknown_email.status_code == status.HTTP_401_UNAUTHORIZED
        # Identical error message prevents account enumeration
        assert resp_unknown_email.json()["message"] == resp_wrong_pwd.json()["message"]

        # Verify failed login audit event was recorded
        failed_event = AuditEvent.objects.filter(
            action=AuditAction.LOGIN_FAILED,
            details__email=resident_user.email,
        ).first()
        assert failed_event is not None

    def test_tc03_rate_limiting_throttle_after_five_failures(self, api_client: APIClient, resident_user: User):
        """TC-03: Sixth consecutive failed login attempt within 1 minute returns 429 (NFR-02, AC-01.3)."""
        for _ in range(5):
            resp = api_client.post(
                "/api/auth/login",
                {"email": resident_user.email, "password": "BadPassword#123"},
                format="json",
            )
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED

        # 6th attempt should be throttled (HTTP 429)
        resp_throttled = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "BadPassword#123"},
            format="json",
        )
        assert resp_throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Too many failed login attempts" in resp_throttled.json()["message"]

    def test_tc04_deactivated_user_cannot_sign_in_or_use_session(
        self, api_client: APIClient, resident_user: User
    ):
        """TC-04: Deactivated user rejected at sign-in; active session terminated on deactivation (BR-07, AC-01.4)."""
        # Case A: User already deactivated attempts sign-in
        resident_user.is_active = False
        resident_user.save()

        resp = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp.json()["message"] == "Invalid email or password."

        # Case B: User signed in, then deactivated &rarr; next API call rejected
        resident_user.is_active = True
        resident_user.save()

        login_resp = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK

        # Call /api/me while active &rarr; 200
        assert api_client.get("/api/me").status_code == status.HTTP_200_OK

        # Deactivate user
        resident_user.is_active = False
        resident_user.save()

        # Next call with open session rejected
        me_resp = api_client.get("/api/me")
        assert me_resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_tc05_temporary_password_forced_change(self, api_client: APIClient, resident_user: User):
        """TC-05: Temporary password flag forces password change; weak passwords rejected (FR-02)."""
        resident_user.must_change_password = True
        resident_user.save()

        # Sign in succeeds, must_change_password is true in profile
        login_resp = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK
        assert login_resp.json()["must_change_password"] is True

        # Attempt to change to weak password (< 10 chars)
        weak_resp = api_client.post(
            "/api/auth/password",
            {"current_password": "ValidPassword#123", "new_password": "short"},
            format="json",
        )
        assert weak_resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Change to valid strong password (>= 10 chars)
        strong_resp = api_client.post(
            "/api/auth/password",
            {"current_password": "ValidPassword#123", "new_password": "NewStrongPass#2026"},
            format="json",
        )
        assert strong_resp.status_code == status.HTTP_200_OK

        # Verify must_change_password cleared
        resident_user.refresh_from_db()
        assert resident_user.must_change_password is False

    def test_nt02_argon2id_hashing_and_cookie_policy(self, resident_user: User, api_client: APIClient):
        """NT-02: Passwords stored strictly as Argon2id hashes; cookie security verified (NFR-02)."""
        # 1. Database inspection
        hasher = identify_hasher(resident_user.password)
        assert hasher.algorithm == "argon2", f"Expected argon2 hasher, got {hasher.algorithm}"
        assert resident_user.password.startswith("argon2$argon2id$")

        # 2. Cookie security inspection
        login_resp = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK
        session_cookie = login_resp.cookies.get("sessionid")
        assert session_cookie is not None
        assert session_cookie.get("httponly") is True
        assert session_cookie.get("samesite") == "Lax"

    def test_st05_session_invalidation_after_logout(self, api_client: APIClient, resident_user: User):
        """ST-05: Reusing session cookie after sign-out returns 401 Unauthorized (NFR-02)."""
        # Login
        login_resp = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        assert login_resp.status_code == status.HTTP_200_OK

        # Call /api/me &rarr; 200
        assert api_client.get("/api/me").status_code == status.HTTP_200_OK

        # Logout
        logout_resp = api_client.post("/api/auth/logout")
        assert logout_resp.status_code == status.HTTP_200_OK

        # Reuse session &rarr; 401
        assert api_client.get("/api/me").status_code == status.HTTP_401_UNAUTHORIZED
