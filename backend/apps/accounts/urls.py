"""URL routing for accounts and authentication endpoints (Section 6.3)."""

from django.urls import path

from apps.accounts.views import (
    ChangePasswordView,
    CsrfTokenView,
    LoginView,
    LogoutView,
    MeView,
    UserAdminCsvImportView,
    UserAdminDetailUpdateView,
    UserAdminListCreateView,
    UserAdminResetPasswordView,
)

urlpatterns = [
    # Auth endpoints (no trailing slashes per Section 6.3)
    path("auth/csrf", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/password", ChangePasswordView.as_view(), name="auth-password"),
    # Current user
    path("me", MeView.as_view(), name="user-me"),
    # User Administration & CSV Import (FR-03, FR-04, SCR-11, SCR-12)
    path("users/", UserAdminListCreateView.as_view(), name="admin-user-list-create"),
    path("users/<int:pk>/", UserAdminDetailUpdateView.as_view(), name="admin-user-detail"),
    path("users/<int:pk>/reset-password/", UserAdminResetPasswordView.as_view(), name="admin-user-reset-password"),
    path("users/import-csv/", UserAdminCsvImportView.as_view(), name="admin-user-import-csv"),
]
