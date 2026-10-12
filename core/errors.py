import logging

from django.http import JsonResponse
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class APIError(APIException):
    def __init__(self, code, message, status=400, details=None):
        self.status_code = status
        self.code, self.message = code, message
        self.details = [] if details is None else details
        super().__init__(message)


def envelope(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details or []}}


def exception_handler(exc, context):
    if isinstance(exc, APIError):
        return Response(envelope(exc.code, exc.message, exc.details), status=exc.status_code)
    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(envelope("INTERNAL_ERROR", "An unexpected error occurred."), status=500)
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
        response.status_code, "VALIDATION_ERROR"
    )
    data = response.data
    message = (
        str(data.get("detail", "Invalid request."))
        if isinstance(data, dict)
        else "Invalid request."
    )
    response.data = envelope(code, message, data if isinstance(data, list) else [data])
    return response


def not_found(request, exception=None):
    return JsonResponse(envelope("NOT_FOUND", "Resource not found."), status=404)


def server_error(request):
    return JsonResponse(envelope("INTERNAL_ERROR", "An unexpected error occurred."), status=500)
