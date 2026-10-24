import os
import subprocess
import sys

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from .models import RiskRule

pytestmark = pytest.mark.django_db
URL = "/api/v1/risk-rules"


@pytest.fixture
def manager(django_user_model):
    user = django_user_model.objects.create_user(
        "risk-manager", password="test-only-password"
    )
    user.groups.add(Group.objects.get_or_create(name="manager")[0])
    return user


@pytest.fixture
def manager_client(manager):
    client = APIClient(enforce_csrf_checks=True)
    assert client.login(username=manager.username, password="test-only-password")
    return client


def make_rule(**kwargs):
    fields = {"name": "Test rule", "type": RiskRule.Type.AMOUNT_LIMIT}
    fields.update(kwargs)
    return RiskRule.objects.create(**fields)


def test_manager_reads_stored_configuration(manager_client):
    rule = make_rule(parameters={"max_amount_irr": 5000000}, enabled=False, revision=2)
    response = manager_client.get(URL, HTTP_X_CORRELATION_ID="rules-list-test")
    assert response.status_code == 200
    assert response["X-Correlation-ID"] == "rules-list-test"
    assert response.json() == {
        "items": [
            {
                "id": str(rule.id),
                "name": rule.name,
                "type": "AMOUNT_LIMIT",
                "parameters": {"max_amount_irr": 5000000},
                "enabled": False,
                "revision": 2,
                "effective_at": rule.effective_at.isoformat().replace("+00:00", "Z"),
                "created_at": rule.created_at.isoformat().replace("+00:00", "Z"),
                "updated_at": rule.updated_at.isoformat().replace("+00:00", "Z"),
            }
        ],
        "next_cursor": None,
    }
    assert rule.id.version == 7


def test_empty_configuration_has_explicit_empty_page(manager_client):
    assert manager_client.get(URL).json() == {"items": [], "next_cursor": None}


def test_anonymous_session_is_denied():
    response = APIClient().get(URL)
    assert response.status_code == 403
    assert response["Content-Type"] == "application/problem+json"
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("role", [None, "operator", "analyst"])
def test_non_managers_are_denied(role, django_user_model):
    user = django_user_model.objects.create_user("other-user")
    if role:
        user.groups.add(Group.objects.get_or_create(name=role)[0])
    client = APIClient()
    client.force_login(user)
    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_superuser_without_manager_group_is_denied(django_user_model):
    user = django_user_model.objects.create_user(
        "admin", is_staff=True, is_superuser=True
    )
    client = APIClient()
    client.force_login(user)
    response = client.get(URL)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_inactive_manager_session_is_denied(manager_client, manager):
    manager.is_active = False
    manager.save(update_fields=["is_active"])
    response = manager_client.get(URL)
    assert response.status_code == 403
    assert response.json()["code"] == "UNAUTHORIZED"


def test_page_limit_is_capped_at_200(manager_client):
    RiskRule.objects.bulk_create(
        [RiskRule(name=f"Rule {i}", type=RiskRule.Type.BLOCKLIST) for i in range(201)]
    )
    response = manager_client.get(URL, {"limit": 999})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 200
    assert response.json()["next_cursor"]


def test_cursor_pages_have_no_duplicate_or_missing_rules(manager_client):
    rules = [make_rule(name=f"Rule {i}") for i in range(3)]
    # Exercise equal timestamps: UUID is the deterministic secondary ordering.
    RiskRule.objects.update(created_at=timezone.now())
    ids = []
    cursor = None
    for _ in range(3):
        query = {"limit": 1}
        if cursor:
            query["cursor"] = cursor
        response = manager_client.get(URL, query)
        assert response.status_code == 200
        ids.extend(item["id"] for item in response.json()["items"])
        cursor = response.json()["next_cursor"]
    assert cursor is None
    assert ids == sorted((str(rule.id) for rule in rules), reverse=True)


def test_bad_cursor_returns_problem_details(manager_client):
    response = manager_client.get(URL, {"cursor": "not-a-valid-cursor"})
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_authenticated_unsafe_requests_still_require_csrf(manager_client):
    response = manager_client.post(URL, {}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert RiskRule.objects.count() == 0


def test_endpoint_does_not_allow_writes(manager):
    client = APIClient()
    client.force_login(manager)
    response = client.post(URL, {"name": "Unauthorized write"}, format="json")
    assert response.status_code == 405
    assert RiskRule.objects.count() == 0


@pytest.mark.parametrize("invalid", [{"type": "UNKNOWN"}, {"revision": 0}])
def test_database_rejects_invalid_configuration(invalid):
    with transaction.atomic(), pytest.raises(IntegrityError):
        make_rule(**invalid)


def test_explicit_development_fixture_is_repeatable(manager_client):
    call_command("loaddata", "dev_risk_rules", verbosity=0)
    call_command("loaddata", "dev_risk_rules", verbosity=0)
    assert RiskRule.objects.count() == 2
    assert not RiskRule.objects.filter(enabled=True).exists()
    assert len(manager_client.get(URL).json()["items"]) == 2


@pytest.mark.django_db(transaction=True)
def test_configuration_survives_a_new_python_process():
    rule = make_rule(name="Persistent rule")
    environment = os.environ.copy()
    environment["POSTGRES_DB"] = connection.settings_dict["NAME"]
    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "shell",
            "-c",
            f"from rules.models import RiskRule; assert RiskRule.objects.get(pk='{rule.id}').name == 'Persistent rule'",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_schema_exposes_actual_cursor_envelope():
    schema = SchemaGenerator().get_schema(request=None, public=True)
    operation = schema["paths"][URL]["get"]
    assert operation["security"] == [{"cookieAuth": []}]
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    definition = schema["components"]["schemas"][response["$ref"].rsplit("/", 1)[1]]
    assert set(definition["properties"]) == {"items", "next_cursor"}
    assert "application/problem+json" in operation["responses"]["403"]["content"]
