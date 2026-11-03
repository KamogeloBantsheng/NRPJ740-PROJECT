"""Views for user authentication, password management, and current profile (FR-01, FR-02)."""

from config.exceptions import NotFoundException, ValidationException
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MfaDisableSerializer,
    MfaEnableSerializer,
    MfaVerifySerializer,
    UserAdminItemSerializer,
    UserCreateSerializer,
    UserMeSerializer,
    UserUpdateSerializer,
)
from apps.accounts.services import AuthService, MFAService, UserAdminService, UserImportService


class CsrfTokenView(APIView):
    """Issues CSRF cookie token for single-origin web client writes."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        operation_id="api_auth_csrf",
        summary="Get CSRF token",
        description="Issues CSRF cookie token for single-origin web client writes.",
        responses={
            200: inline_serializer(
                name="CsrfTokenResponse",
                fields={"csrfToken": serializers.CharField()},
            )
        },
    )
    def get(self, request: Request) -> Response:
        token = get_token(request)
        return Response({"csrfToken": token})


class LoginView(APIView):
    """Authenticates user, starts 8-hour session, and rotates session ID (FR-01, SCR-01)."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        operation_id="api_auth_login",
        summary="User sign-in",
        description="Authenticates user, starts 8-hour session, and rotates session ID (FR-01, SCR-01).",
        request=LoginSerializer,
        responses={200: UserMeSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, requires_mfa, mfa_token = AuthService.authenticate(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            request=request,
        )

        if requires_mfa:
            return Response(
                {
                    "requires_mfa": True,
                    "mfa_token": mfa_token,
                    "email": user.email,
                },
                status=status.HTTP_200_OK,
            )

        return Response(UserMeSerializer(user).data, status=status.HTTP_200_OK)


class MfaVerifyView(APIView):
    """Verifies 6-digit TOTP code or backup code to complete authentication."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        operation_id="api_auth_mfa_verify",
        summary="Verify MFA code during login",
        description="Validates TOTP 6-digit code or backup code, establishes user session.",
        request=MfaVerifySerializer,
        responses={200: UserMeSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = MfaVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = MFAService.verify_login_mfa(
            mfa_token=serializer.validated_data["mfa_token"],
            code=serializer.validated_data["code"],
            request=request,
        )

        return Response(UserMeSerializer(user).data, status=status.HTTP_200_OK)


class MfaSetupView(APIView):
    """Generates a new TOTP secret and provisioning URI for MFA enrollment."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_auth_mfa_setup",
        summary="Generate TOTP setup secret",
        description="Generates a temporary TOTP key and provisioning URI to scan in an authenticator app.",
        responses={
            200: inline_serializer(
                name="MfaSetupResponse",
                fields={
                    "secret": serializers.CharField(),
                    "provisioning_uri": serializers.CharField(),
                    "setup_token": serializers.CharField(),
                },
            )
        },
    )
    def post(self, request: Request) -> Response:
        data = MFAService.generate_setup(request.user)
        return Response(data, status=status.HTTP_200_OK)


class MfaEnableView(APIView):
    """Confirms initial TOTP code to activate MFA and generates 8 emergency backup codes."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_auth_mfa_enable",
        summary="Activate MFA with confirmation code",
        description="Validates code against setup_token, activates MFA, returns 8 one-time backup codes.",
        request=MfaEnableSerializer,
        responses={
            200: inline_serializer(
                name="MfaEnableResponse",
                fields={
                    "message": serializers.CharField(),
                    "backup_codes": serializers.ListField(child=serializers.CharField()),
                },
            )
        },
    )
    def post(self, request: Request) -> Response:
        serializer = MfaEnableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        backup_codes = MFAService.enable_mfa(
            user=request.user,
            code=serializer.validated_data["code"],
            setup_token=serializer.validated_data["setup_token"],
        )

        return Response(
            {
                "message": "Two-factor authentication successfully enabled.",
                "backup_codes": backup_codes,
            },
            status=status.HTTP_200_OK,
        )


class MfaDisableView(APIView):
    """Deactivates MFA after validating user's current password."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_auth_mfa_disable",
        summary="Disable two-factor authentication",
        description="Deactivates TOTP and removes backup codes after password confirmation.",
        request=MfaDisableSerializer,
        responses={
            200: inline_serializer(
                name="MfaDisableResponse",
                fields={"message": serializers.CharField()},
            )
        },
    )
    def post(self, request: Request) -> Response:
        serializer = MfaDisableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        MFAService.disable_mfa(
            user=request.user,
            password=serializer.validated_data["password"],
        )

        return Response(
            {"message": "Two-factor authentication has been disabled."},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """Invalidates user session and clears authentication cookies (FR-01)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_auth_logout",
        summary="User sign-out",
        description="Invalidates user session and clears authentication cookies (FR-01).",
        request=None,
        responses={
            200: inline_serializer(
                name="LogoutResponse",
                fields={"message": serializers.CharField()},
            )
        },
    )
    def post(self, request: Request) -> Response:
        AuthService.logout(request)
        return Response({"message": "Successfully signed out."}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """Changes password for authenticated user with Argon2id hashing (FR-02, SCR-02)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_auth_change_password",
        summary="Change password",
        description="Changes password for authenticated user with Argon2id hashing (FR-02, SCR-02).",
        request=ChangePasswordSerializer,
        responses={
            200: inline_serializer(
                name="ChangePasswordResponse",
                fields={"message": serializers.CharField()},
            )
        },
    )
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.change_password(
            user=request.user,
            current_password=serializer.validated_data.get("current_password"),
            new_password=serializer.validated_data["new_password"],
            request=request._request,
        )

        return Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """Retrieves profile and role for current authenticated user (FR-01)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        operation_id="api_auth_me",
        summary="Current user profile",
        description="Retrieves profile and role for current authenticated user (FR-01).",
        responses={200: UserMeSerializer},
    )
    def get(self, request: Request) -> Response:
        return Response(UserMeSerializer(request.user).data, status=status.HTTP_200_OK)


class UserAdminListCreateView(APIView):
    """List users or create a new user account (FR-03, SCR-11)."""

    permission_classes = (IsAuthenticated, IsAdmin)

    @extend_schema(
        operation_id="api_users_list",
        summary="List users",
        description="List users with optional search, role, status and residence filters (FR-03, SCR-11).",
        responses={200: UserAdminItemSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        search = request.query_params.get("search", "")
        role = request.query_params.get("role", "")
        is_active_param = request.query_params.get("is_active")
        is_active = None
        if is_active_param is not None:
            if is_active_param.lower() in ("true", "1"):
                is_active = True
            elif is_active_param.lower() in ("false", "0"):
                is_active = False

        residence_id = request.query_params.get("residence_id")
        res_id = int(residence_id) if residence_id and residence_id.isdigit() else None

        users = UserAdminService.list_users(
            search=search,
            role=role,
            is_active=is_active,
            residence_id=res_id,
        )
        serializer = UserAdminItemSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="api_users_create",
        summary="Create user account",
        description="Create a single user account with auto-generated temporary password (FR-03, SCR-11).",
        request=UserCreateSerializer,
        responses={
            201: inline_serializer(
                name="UserCreateResponse",
                fields={
                    "user": UserAdminItemSerializer(),
                    "temporary_password": serializers.CharField(),
                },
            )
        },
    )
    def post(self, request: Request) -> Response:
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationException("Invalid user payload.", fields=serializer.errors)

        data = serializer.validated_data
        user, temp_pwd = UserAdminService.create_user(
            actor=request.user,
            email=data["email"],
            full_name=data["full_name"],
            role=data["role"],
            residence_id=data.get("residence_id"),
            assigned_location_id=data.get("assigned_location_id"),
            student_number=data.get("student_number"),
        )

        return Response(
            {
                "user": UserAdminItemSerializer(user).data,
                "temporary_password": temp_pwd,
            },
            status=status.HTTP_201_CREATED,
        )


class UserAdminDetailUpdateView(APIView):
    """Retrieve or update a user profile, role, or active status (FR-03, BR-07, SCR-11)."""

    permission_classes = (IsAuthenticated, IsAdmin)

    @extend_schema(
        operation_id="api_users_retrieve",
        summary="Retrieve user details",
        description="Retrieve profile details for a specific user (FR-03, SCR-11).",
        responses={200: UserAdminItemSerializer},
    )
    def get(self, request: Request, pk: int) -> Response:
        user = User.objects.filter(id=pk).first()
        if not user:
            raise NotFoundException(f"User {pk} not found.")
        return Response(UserAdminItemSerializer(user).data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="api_users_patch",
        summary="Update user details",
        description="Update profile, role, active flag, residence, or student number (FR-03, BR-07, SCR-11).",
        request=UserUpdateSerializer,
        responses={200: UserAdminItemSerializer},
    )
    def patch(self, request: Request, pk: int) -> Response:
        user = User.objects.filter(id=pk).first()
        if not user:
            raise NotFoundException(f"User {pk} not found.")

        serializer = UserUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            raise ValidationException("Invalid user update payload.", fields=serializer.errors)

        data = serializer.validated_data
        updated_user = UserAdminService.update_user(
            actor=request.user,
            user=user,
            full_name=data.get("full_name"),
            role=data.get("role"),
            is_active=data.get("is_active"),
            residence_id=data.get("residence_id"),
            assigned_location_id=data.get("assigned_location_id"),
            student_number=data.get("student_number"),
        )

        return Response(UserAdminItemSerializer(updated_user).data, status=status.HTTP_200_OK)


class UserAdminResetPasswordView(APIView):
    """Reset a user's password to a newly generated temporary password (FR-03, SCR-11)."""

    permission_classes = (IsAuthenticated, IsAdmin)

    @extend_schema(
        operation_id="api_users_reset_password",
        summary="Reset user password",
        description="Generate a new temporary password and force password change on next login (FR-03, SCR-11).",
        request=None,
        responses={
            200: inline_serializer(
                name="UserResetPasswordResponse",
                fields={
                    "message": serializers.CharField(),
                    "temporary_password": serializers.CharField(),
                },
            )
        },
    )
    def post(self, request: Request, pk: int) -> Response:
        user = User.objects.filter(id=pk).first()
        if not user:
            raise NotFoundException(f"User {pk} not found.")

        temp_pwd = UserAdminService.reset_password(actor=request.user, user=user)

        return Response(
            {
                "message": f"Password for {user.email} was reset successfully.",
                "temporary_password": temp_pwd,
            },
            status=status.HTTP_200_OK,
        )


class UserAdminCsvImportView(APIView):
    """All-or-nothing batch import of resident accounts from CSV file (FR-04, SCR-12)."""

    permission_classes = (IsAuthenticated, IsAdmin)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        operation_id="api_users_import_csv",
        summary="Batch import residents CSV",
        description="All-or-nothing batch import of resident accounts from CSV file (FR-04, SCR-12).",
        request=None,
        responses={
            201: inline_serializer(
                name="UserImportCsvResponse",
                fields={
                    "total_rows": serializers.IntegerField(),
                    "imported_count": serializers.IntegerField(),
                    "created_accounts": serializers.ListField(child=serializers.DictField()),
                    "credentials_file_content": serializers.CharField(),
                },
            )
        },
    )
    def post(self, request: Request) -> Response:
        file_obj = request.FILES.get("file")
        if file_obj:
            file_bytes = file_obj.read()
        elif "file" in request.data:
            val = request.data["file"]
            if isinstance(val, bytes):
                file_bytes = val
            elif isinstance(val, str):
                file_bytes = val.encode("utf-8")
            else:
                file_bytes = val.read()
        else:
            raise ValidationException(
                "No CSV file provided for import.",
                fields={"file": ["Please select or upload a CSV file."]},
            )

        result = UserImportService.import_residents_csv(
            actor=request.user,
            csv_file_bytes=file_bytes,
        )

        return Response(result, status=status.HTTP_201_CREATED)


