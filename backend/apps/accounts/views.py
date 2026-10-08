"""Views for user authentication, password management, and current profile (FR-01, FR-02)."""

from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import ChangePasswordSerializer, LoginSerializer, UserMeSerializer
from apps.accounts.services import AuthService


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
