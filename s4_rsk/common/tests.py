import os
import runpy
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db.utils import OperationalError
from django.test import override_settings
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient

from common.exceptions import LabBankAPIException


@api_view(["GET"])
@permission_classes([AllowAny])
def conflict_view(request):
    raise LabBankAPIException(
        code="CONFLICT",
        title="Conflict",
        detail="A record already exists.",
        status_code=409,
        type_slug="conflict",
    )


urlpatterns = [path("conflict", conflict_view)]


def test_domain_exception_preserves_detail():
    error = LabBankAPIException("CONFLICT", "Conflict", "Duplicate", 409)
    assert str(error) == "Duplicate"
    assert error.args == ("Duplicate",)


def test_domain_conflict_is_a_problem_response():
    with override_settings(
        ROOT_URLCONF=__name__,
        REST_FRAMEWORK={
            "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
            "EXCEPTION_HANDLER": "common.exceptions.rfc9457_exception_handler",
        },
    ):
        response = APIClient().get("/conflict", HTTP_X_CORRELATION_ID="test-conflict")
    assert response.status_code == 409
    assert response["Content-Type"] == "application/problem+json"
    assert response.json() == {
        "type": "https://errors.labbank.example/conflict",
        "title": "Conflict",
        "status": 409,
        "code": "CONFLICT",
        "detail": "A record already exists.",
        "correlation_id": "test-conflict",
    }
    assert response["X-Correlation-ID"] == "test-conflict"


def test_health_is_public_and_does_not_access_database():
    with patch("common.views.connections") as connections:
        response = APIClient().get("/health")
    connections.__getitem__.assert_not_called()
    assert response.status_code == 200
    assert response.json() == {"status": "UP", "service": "s4-rsk"}
    assert response["X-Correlation-ID"]


def test_ready_reports_success_after_database_query():
    with patch("common.views.connections") as connections:
        response = APIClient().get("/ready")
    cursor = (
        connections.__getitem__.return_value.cursor.return_value.__enter__.return_value
    )
    cursor.execute.assert_called_once_with("SELECT 1;")
    assert response.status_code == 200
    assert response.json() == {
        "status": "READY",
        "service": "s4-rsk",
        "database": "CONNECTED",
    }


@pytest.mark.django_db
def test_ready_connects_to_real_postgresql():
    from django.db import connection

    assert connection.vendor == "postgresql"
    response = APIClient().get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "CONNECTED"


def test_database_failure_returns_503_without_internal_error_text():
    with patch("common.views.connections") as connections:
        connections.__getitem__.return_value.cursor.side_effect = OperationalError(
            "private-database-password"
        )
        response = APIClient().get("/ready", HTTP_X_CORRELATION_ID="test-ready")
    assert response.status_code == 503
    assert response["Content-Type"] == "application/problem+json"
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert response.json()["correlation_id"] == "test-ready"
    assert "private-database-password" not in response.content.decode()


@pytest.mark.parametrize("url", ["/health", "/ready"])
def test_probes_reject_post(url):
    response = APIClient().post(url)
    assert response.status_code == 405
    assert response.json()["status"] == 405


def test_openapi_matches_probe_responses():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    validate_schema(schema)
    assert schema["openapi"] == "3.1.0"
    for url in ("/health", "/ready"):
        operation = schema["paths"][url]["get"]
        assert not operation.get("security")
        assert "application/json" in operation["responses"]["200"]["content"]
        assert "X-Correlation-ID" in operation["responses"]["200"]["headers"]
    error_response = schema["paths"]["/ready"]["get"]["responses"]["503"]
    assert "application/problem+json" in error_response["content"]


@pytest.mark.parametrize(
    "secret", [None, "unsafe-dev-secret-key", "django-insecure-example"]
)
def test_non_development_requires_real_secret(secret):
    environment = {"DEBUG": "False"}
    if secret is not None:
        environment["SECRET_KEY"] = secret
    with (
        patch.dict(os.environ, environment, clear=True),
        patch("pathlib.Path.exists", return_value=False),
        pytest.raises(ImproperlyConfigured),
    ):
        runpy.run_path(str(Path(__file__).resolve().parents[1] / "config/settings.py"))
