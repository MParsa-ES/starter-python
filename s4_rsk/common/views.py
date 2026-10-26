from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .exceptions import LabBankAPIException
from .schema import CORRELATION_HEADERS
from .serializers import HealthSerializer, ProblemSerializer, ReadySerializer


@extend_schema(
    auth=[],
    responses={200: HealthSerializer},
    parameters=CORRELATION_HEADERS,
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health_view(request):
    """GEN-10: Reports process liveness."""
    return Response(
        {"status": "UP", "service": settings.SERVICE_NAME}, status=status.HTTP_200_OK
    )


@extend_schema(
    auth=[],
    responses={
        200: ReadySerializer,
        (503, "application/problem+json"): ProblemSerializer,
    },
    parameters=CORRELATION_HEADERS,
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def ready_view(request):
    """GEN-10: Reports readiness of dependencies (PostgreSQL database)."""
    try:
        db_conn = connections["default"]
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
    except OperationalError as exc:
        raise LabBankAPIException(
            code="SERVICE_UNAVAILABLE",
            title="Database dependency unavailable",
            detail="PostgreSQL connection check failed.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            type_slug="service-unavailable",
        ) from exc

    return Response(
        {"status": "READY", "service": settings.SERVICE_NAME, "database": "CONNECTED"},
        status=status.HTTP_200_OK,
    )
