"""Provider API tests for the probes against openapi/s4_rsk.yaml (no authentication needed)."""

from unittest.mock import patch

import pytest
from django.db import OperationalError
from rest_framework.test import APIClient

from .openapi_contract import assert_response_matches

pytestmark = pytest.mark.openapi


def test_health_matches_contract():
    response = APIClient().get("/health")
    assert_response_matches(response, path_template="/health", method="get")
    assert response.status_code == 200


@pytest.mark.django_db
def test_ready_matches_contract_on_real_postgresql():
    response = APIClient().get("/ready")
    assert_response_matches(response, path_template="/ready", method="get")
    assert response.status_code == 200


def test_ready_failure_is_documented_problem_details():
    with patch("common.views.connections") as connections:
        connections.__getitem__.return_value.cursor.side_effect = OperationalError("down")
        response = APIClient().get("/ready")
    assert_response_matches(response, path_template="/ready", method="get")
    assert response.status_code == 503
    assert response["Content-Type"] == "application/problem+json"
