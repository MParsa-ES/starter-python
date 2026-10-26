from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .middleware import get_correlation_id


class LabBankAPIException(Exception):
    """Base domain exception for custom S4-RSK RFC 9457 errors (e.g., 409 CONFLICT)."""

    def __init__(
        self,
        code: str,
        title: str,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        type_slug: str = "error",
    ):
        self.code = code
        self.title = title
        self.detail = detail
        self.status_code = status_code
        self.type_slug = type_slug
        super().__init__(detail)


def rfc9457_exception_handler(exc, context):
    """
    GEN-06: Returns errors in RFC 9457 format with Content-Type: application/problem+json.
    """
    correlation_id = get_correlation_id()

    if isinstance(exc, LabBankAPIException):
        payload = {
            "type": f"https://errors.labbank.example/{exc.type_slug}",
            "title": exc.title,
            "status": exc.status_code,
            "code": exc.code,
            "detail": exc.detail,
            "correlation_id": correlation_id,
        }
        return Response(
            payload,
            status=exc.status_code,
            content_type="application/problem+json",
        )

    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, ValidationError):
            code = "VALIDATION_ERROR"
            title = "Invalid or incomplete input"
            type_slug = "validation-error"
            detail = str(response.data)
        elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            code = "UNAUTHORIZED"
            title = "Authentication required or failed"
            type_slug = "unauthorized"
            detail = str(exc.detail)
        elif isinstance(exc, PermissionDenied):
            code = "FORBIDDEN"
            title = "Access to resource is forbidden"
            type_slug = "forbidden"
            detail = str(exc.detail)
        elif isinstance(exc, (NotFound, Http404)):
            code = "NOT_FOUND"
            title = "Resource not found"
            type_slug = "not-found"
            detail = str(getattr(exc, "detail", "The requested resource was not found."))
        else:
            code = getattr(exc, "default_code", "ERROR").upper()
            title = "Request could not be processed"
            type_slug = "problem"
            detail = str(response.data)

        problem_body = {
            "type": f"https://errors.labbank.example/{type_slug}",
            "title": title,
            "status": response.status_code,
            "code": code,
            "detail": detail,
            "correlation_id": correlation_id,
        }
        response.data = problem_body
        response.content_type = "application/problem+json"
        return response

    return None
