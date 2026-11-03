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
    assigned_location_name = serializers.SerializerMethodField()

    def get_assigned_location_name(self, obj: User) -> str | None:
        if obj.assigned_location:
            loc = obj.assigned_location
            return f"Block {loc.block} Fl {loc.floor} ({loc.label})"
        return None

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
            "assigned_location",
            "assigned_location_name",
            "must_change_password",
            "is_active",
            "is_mfa_enabled",
            "created_at",
            "last_login",
        )
        read_only_fields = fields


class MfaVerifySerializer(serializers.Serializer):
    """Payload to verify 6-digit TOTP code or backup code during sign-in."""

    mfa_token = serializers.CharField(required=True)
    code = serializers.CharField(required=True, trim_whitespace=True)


class MfaEnableSerializer(serializers.Serializer):
    """Payload to confirm TOTP code and enable 2FA."""

    setup_token = serializers.CharField(required=True)
    code = serializers.CharField(required=True, trim_whitespace=True)


class MfaDisableSerializer(serializers.Serializer):
    """Payload to disable 2FA after password verification."""

    password = serializers.CharField(required=True, write_only=True, trim_whitespace=False)


class UserAdminItemSerializer(serializers.ModelSerializer):
    """User item detail for Admin User Management table (SCR-11)."""

    residence_name = serializers.CharField(source="residence.name", read_only=True, default=None)
    assigned_location_name = serializers.SerializerMethodField()
    active_work_orders_count = serializers.IntegerField(read_only=True, default=0)

    def get_assigned_location_name(self, obj: User) -> str | None:
        if obj.assigned_location:
            loc = obj.assigned_location
            return f"Block {loc.block} Fl {loc.floor} ({loc.label})"
        return None

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
            "assigned_location",
            "assigned_location_name",
            "is_active",
            "is_mfa_enabled",
            "must_change_password",
            "created_at",
            "last_login",
            "active_work_orders_count",
        )
        read_only_fields = fields


class UserCreateSerializer(serializers.Serializer):
    """Payload for creating a new user by an administrator (FR-03, SCR-11)."""

    email = serializers.EmailField(required=True)
    full_name = serializers.CharField(max_length=150, required=True)
    role = serializers.ChoiceField(choices=User._meta.get_field("role").choices, required=True)
    residence_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_location_id = serializers.IntegerField(required=False, allow_null=True)
    student_number = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)


class UserUpdateSerializer(serializers.Serializer):
    """Payload for updating user profile, role, or active status (FR-03, BR-07, SCR-11)."""

    full_name = serializers.CharField(max_length=150, required=False)
    role = serializers.ChoiceField(choices=User._meta.get_field("role").choices, required=False)
    is_active = serializers.BooleanField(required=False)
    residence_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_location_id = serializers.IntegerField(required=False, allow_null=True)
    student_number = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True)

