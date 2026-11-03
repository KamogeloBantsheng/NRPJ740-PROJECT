"""Test suite for Enhanced Security Hardening:
1. CSV Formula Injection Defense (CWE-1236)
2. Progressive Exponential Backoff Lockout (NFR-02)
3. Multi-Factor Authentication (TOTP / 2FA & Backup Codes)
"""

import io

import pyotp
import pytest
from apps.accounts.models import User
from apps.accounts.services import AuthService, sanitize_csv_cell
from apps.locations.models import Residence
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestEnhancedSecurityHardening:
    """Tests covering enhanced security features."""

    def test_csv_formula_injection_sanitization(self, admin_client: APIClient, residence: Residence):
        """Verify leading formula triggers (=, +, -, @) are sanitized with an apostrophe."""
        # Unit test on helper
        assert sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
        assert sanitize_csv_cell("@SUM(1+1)") == "'@SUM(1+1)"
        assert sanitize_csv_cell("+123456789") == "'+123456789"
        assert sanitize_csv_cell("-2+3") == "'-2+3"
        assert sanitize_csv_cell("Normal Name") == "Normal Name"
        assert sanitize_csv_cell("202300099") == "202300099"

        # Integration test via CSV import
        csv_content = (
            "full_name,email,student_number,room_number\n"
            "=cmd|' /C calc'!A0,malicious.user@spu.ac.za,@202399999,101\n"
        )
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "residents.csv"

        resp = admin_client.post(
            "/api/users/import-csv/",
            {"file": csv_file},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED

        created_user = User.objects.get(email="malicious.user@spu.ac.za")
        assert created_user.full_name == "'=cmd|' /C calc'!A0"
        assert created_user.student_number == "'@202399999"

    def test_progressive_exponential_backoff_lockout_tiers(self):
        """Verify lockout duration calculation tiers."""
        assert AuthService.calculate_lockout_duration(0) == 0
        assert AuthService.calculate_lockout_duration(4) == 0
        assert AuthService.calculate_lockout_duration(5) == 60      # Tier 1: 1 min
        assert AuthService.calculate_lockout_duration(9) == 60
        assert AuthService.calculate_lockout_duration(10) == 900    # Tier 2: 15 min
        assert AuthService.calculate_lockout_duration(14) == 900
        assert AuthService.calculate_lockout_duration(15) == 3600   # Tier 3: 1 hour
        assert AuthService.calculate_lockout_duration(19) == 3600
        assert AuthService.calculate_lockout_duration(20) == 86400  # Tier 4: 24 hours

    def test_mfa_full_lifecycle_enrollment_login_and_backup_code(
        self, api_client: APIClient, resident_user: User
    ):
        """Verify full 2FA lifecycle: setup, enable, login with TOTP, backup code login, and disable."""
        # 1. Sign in initially (no MFA enabled)
        resp_login = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        assert resp_login.status_code == status.HTTP_200_OK
        assert "requires_mfa" not in resp_login.json()
        assert "sessionid" in resp_login.cookies

        # 2. Request MFA setup
        resp_setup = api_client.post("/api/auth/mfa/setup", format="json")
        assert resp_setup.status_code == status.HTTP_200_OK
        setup_data = resp_setup.json()
        assert "secret" in setup_data
        assert "setup_token" in setup_data
        assert "provisioning_uri" in setup_data

        # 3. Confirm and enable MFA with valid TOTP code
        totp = pyotp.TOTP(setup_data["secret"])
        valid_code = totp.now()

        resp_enable = api_client.post(
            "/api/auth/mfa/enable",
            {"setup_token": setup_data["setup_token"], "code": valid_code},
            format="json",
        )
        assert resp_enable.status_code == status.HTTP_200_OK
        enable_data = resp_enable.json()
        assert len(enable_data["backup_codes"]) == 8
        first_backup_code = enable_data["backup_codes"][0]

        resident_user.refresh_from_db()
        assert resident_user.is_mfa_enabled is True
        assert resident_user.totp_secret == setup_data["secret"]

        # Log out
        api_client.post("/api/auth/logout", format="json")

        # 4. Sign in with password -> Expect requires_mfa=True and mfa_token
        resp_login_mfa = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        assert resp_login_mfa.status_code == status.HTTP_200_OK
        mfa_challenge = resp_login_mfa.json()
        assert mfa_challenge["requires_mfa"] is True
        assert "mfa_token" in mfa_challenge
        # Session cookie must NOT be active until MFA verification succeeds
        assert not resp_login_mfa.cookies.get("sessionid") or not resp_login_mfa.cookies["sessionid"].value

        # 5. Verify invalid code rejected
        resp_bad_mfa = api_client.post(
            "/api/auth/mfa/verify",
            {"mfa_token": mfa_challenge["mfa_token"], "code": "000000"},
            format="json",
        )
        assert resp_bad_mfa.status_code == status.HTTP_401_UNAUTHORIZED

        # 6. Verify valid TOTP code completes authentication
        fresh_totp_code = totp.now()
        resp_good_mfa = api_client.post(
            "/api/auth/mfa/verify",
            {"mfa_token": mfa_challenge["mfa_token"], "code": fresh_totp_code},
            format="json",
        )
        assert resp_good_mfa.status_code == status.HTTP_200_OK
        assert resp_good_mfa.cookies["sessionid"].value
        assert resp_good_mfa.json()["id"] == resident_user.id

        # Log out
        api_client.post("/api/auth/logout", format="json")

        # 7. Test emergency backup code login
        resp_login_bc = api_client.post(
            "/api/auth/login",
            {"email": resident_user.email, "password": "ValidPassword#123"},
            format="json",
        )
        bc_token = resp_login_bc.json()["mfa_token"]

        resp_bc_verify = api_client.post(
            "/api/auth/mfa/verify",
            {"mfa_token": bc_token, "code": first_backup_code},
            format="json",
        )
        assert resp_bc_verify.status_code == status.HTTP_200_OK
        assert "sessionid" in resp_bc_verify.cookies

        # Verify used backup code is burned
        resident_user.refresh_from_db()
        assert len(resident_user.backup_codes) == 7

        # 8. Disable MFA
        # Wrong password fails
        resp_bad_disable = api_client.post(
            "/api/auth/mfa/disable",
            {"password": "WrongPassword#999"},
            format="json",
        )
        assert resp_bad_disable.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Correct password succeeds
        resp_good_disable = api_client.post(
            "/api/auth/mfa/disable",
            {"password": "ValidPassword#123"},
            format="json",
        )
        assert resp_good_disable.status_code == status.HTTP_200_OK

        resident_user.refresh_from_db()
        assert resident_user.is_mfa_enabled is False
        assert resident_user.totp_secret is None
