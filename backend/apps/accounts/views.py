"""Views for user authentication, password management, and current profile (FR-01, FR-02)."""

from config.exceptions import NotFoundException, ValidationException
from django.middleware.csrf import get_token
from rest_framework import status
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
    UserAdminItemSerializer,
    UserCreateSerializer,
    UserMeSerializer,
    UserUpdateSerializer,
)
from apps.accounts.services import AuthService, UserAdminService, UserImportService


class CsrfTokenView(APIView):
    """Issues CSRF cookie token for single-origin web client writes."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request: Request) -> Response:
        token = get_token(request)
        return Response({"csrfToken": token})


class LoginView(APIView):
    """Authenticates user, starts 8-hour session, and rotates session ID (FR-01, SCR-01)."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = AuthService.authenticate(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            request=request,
        )

        return Response(UserMeSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Invalidates user session and clears authentication cookies (FR-01)."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        AuthService.logout(request)
        return Response({"message": "Successfully signed out."}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """Changes password for authenticated user with Argon2id hashing (FR-02, SCR-02)."""

    permission_classes = (IsAuthenticated,)

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

    def get(self, request: Request) -> Response:
        return Response(UserMeSerializer(request.user).data, status=status.HTTP_200_OK)


class UserAdminListCreateView(APIView):
    """List users or create a new user account (FR-03, SCR-11)."""

    permission_classes = (IsAuthenticated, IsAdmin)

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

    def get(self, request: Request, pk: int) -> Response:
        user = User.objects.filter(id=pk).first()
        if not user:
            raise NotFoundException(f"User {pk} not found.")
        return Response(UserAdminItemSerializer(user).data, status=status.HTTP_200_OK)

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
            student_number=data.get("student_number"),
        )

        return Response(UserAdminItemSerializer(updated_user).data, status=status.HTTP_200_OK)


class UserAdminResetPasswordView(APIView):
    """Reset a user's password to a newly generated temporary password (FR-03, SCR-11)."""

    permission_classes = (IsAuthenticated, IsAdmin)

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


