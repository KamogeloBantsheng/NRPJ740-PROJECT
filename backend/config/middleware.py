"""Project middleware."""

from django.http import HttpRequest, HttpResponse, JsonResponse

# What a user with a temporary password still needs: finding out who they are and leaving,
# and changing the password itself.
PASSWORD_CHANGE_EXEMPT_PATHS = frozenset({
    "/api/health/",
    "/api/auth/csrf",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/password",
    "/api/me",
})


class ForcePasswordChangeMiddleware:
    """Block the API for users on a temporary password until they set their own (FR-02).

    The browser's route guard is only for usability; this is the rule that counts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            request.path.startswith("/api/")
            and request.path not in PASSWORD_CHANGE_EXEMPT_PATHS
            and request.user.is_authenticated
            and request.user.must_change_password
        ):
            return JsonResponse(
                {
                    "code": "PASSWORD_CHANGE_REQUIRED",
                    "message": "You must set a new password before using the system.",
                },
                status=403,
            )
        return self.get_response(request)
