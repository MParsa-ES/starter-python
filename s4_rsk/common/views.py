from django.db import connections
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .exceptions import LabBankAPIException


@api_view(["GET"])
@permission_classes([AllowAny])
def health_view(request):
    """GEN-10: Reports process liveness."""
    return Response({"status": "UP", "service": "s4-rsk"}, status=status.HTTP_200_OK)


@api_view(["GET"])
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
        {"status": "READY", "service": "s4-rsk", "database": "CONNECTED"},
        status=status.HTTP_200_OK,
    )