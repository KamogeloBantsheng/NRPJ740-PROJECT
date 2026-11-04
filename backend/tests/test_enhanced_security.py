"""Test suite for CSV Formula Injection Defense (CWE-1236)."""

import io

import pytest
from apps.accounts.models import User
from apps.accounts.services import sanitize_csv_cell
from apps.locations.models import Residence
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestEnhancedSecurityHardening:
    """Spreadsheet formulas in imported names must be neutralized."""

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
            "full_name,email,student_number\n"
            "=cmd|' /C calc'!A0,malicious.user@spu.ac.za,@202399999\n"
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
