from django.http import JsonResponse

from core.errors import envelope


class APIErrorMiddleware:
    """Keep unmatched API routes JSON even when Django's DEBUG 404 page is enabled."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.path.startswith("/api/")
            and response.status_code >= 400
            and "application/json" not in response.get("Content-Type", "")
        ):
            code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
                response.status_code, "INTERNAL_ERROR"
            )
            return JsonResponse(
                envelope(
                    code,
                    "Resource not found."
                    if response.status_code == 404
                    else "Request could not be completed.",
                ),
                status=response.status_code,
            )
        return response
