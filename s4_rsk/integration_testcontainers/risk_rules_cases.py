import pytest
from django.contrib.auth.models import Group
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from rules.models import RiskRule


@pytest.mark.django_db
def test_manager_reads_rule_from_temporary_postgresql(django_user_model):
    assert connection.vendor == "postgresql"

    # Creating an administrator user for API access.
    manager = django_user_model.objects.create_user(
        username="test-risk-manager",
        password="test-only-password",
    )

    manager_group, _ = Group.objects.get_or_create(name="manager")
    manager.groups.add(manager_group)

    # Creating a risk rule in the temporary database.
    rule = RiskRule.objects.create(
        name="Transfer amount limit",
        type=RiskRule.Type.AMOUNT_LIMIT,
        parameters={"max_amount": 5_000_000},
        enabled=False,
        revision=1,
    )

    # Authenticate with the same JWT mechanism used by the API.
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(manager)}")

    response = client.get("/api/v1/risk-rules")

    # Checking the API response.
    assert response.status_code == 200

    data = response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(rule.id)
    assert data["items"][0]["name"] == "Transfer amount limit"
    assert data["items"][0]["type"] == "AMOUNT_LIMIT"
    assert data["items"][0]["parameters"] == {
        "max_amount": 5_000_000
    }
    assert data["items"][0]["enabled"] is False
    assert data["next_cursor"] is None

@pytest.mark.django_db
def test_rule_list_caps_page_size_at_200(django_user_model):
    manager = django_user_model.objects.create_user(
        username="pagination-manager",
        password="test-only-password",
    )

    manager_group, _ = Group.objects.get_or_create(name="manager")
    manager.groups.add(manager_group)

    RiskRule.objects.bulk_create(
        [
            RiskRule(
                name=f"Rule {index}",
                type=RiskRule.Type.BLOCKLIST,
            )
            for index in range(201)
        ]
    )

    client = APIClient()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(manager)}")

    response = client.get(
        "/api/v1/risk-rules",
        {"limit": 201},
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["items"]) == 200
    assert data["next_cursor"] is not None
