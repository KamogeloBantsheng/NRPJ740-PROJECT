"""Serializers for authentication and user profile endpoints (FR-01, FR-02)."""

from rest_framework import serializers

from apps.accounts.models import User


class LoginSerializer(serializers.Serializer):
    """Payload for user sign-in (SCR-01)."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    """Payload for voluntary or forced password update (SCR-02)."""

    current_password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        trim_whitespace=False,
    )
    new_password = serializers.CharField(required=True, write_only=True, trim_whitespace=False)


class UserMeSerializer(serializers.ModelSerializer):
    """Profile serialization for current authenticated user (/api/me)."""

    residence_name = serializers.CharField(source="residence.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "student_number",
            "role",
            "residence",
            "residence_name",
            "must_change_password",
            "is_active",
            "created_at",
            "last_login",
        )
        read_only_fields = fields
