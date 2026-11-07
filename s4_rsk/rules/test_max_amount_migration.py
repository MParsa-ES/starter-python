from importlib import import_module

import pytest
from django.apps import apps
from django.db import transaction

from .models import RiskRule

migrate_values = import_module("rules.migrations.0005_standardize_max_amount").standardize_max_amount
pytestmark = pytest.mark.django_db


def test_legacy_rule_parameters_are_renamed():
    rule = RiskRule.objects.create(
        name="legacy", type="AMOUNT_LIMIT", parameters={"max_amount_irr": 100, "decision": "REVIEW"}
    )
    migrate_values(apps, None)
    rule.refresh_from_db()
    assert rule.parameters == {"max_amount": 100, "decision": "REVIEW"}


def test_same_values_are_deduplicated():
    rule = RiskRule.objects.create(
        name="legacy", type="AMOUNT_LIMIT", parameters={"max_amount_irr": 100, "max_amount": 100}
    )
    migrate_values(apps, None)
    rule.refresh_from_db()
    assert rule.parameters == {"max_amount": 100}


@pytest.mark.parametrize("new_value", [101, True])
def test_conflicting_values_stop_migration_without_changes(new_value):
    rule = RiskRule.objects.create(
        name="conflict", type="AMOUNT_LIMIT", parameters={"max_amount_irr": 1, "max_amount": new_value}
    )
    with pytest.raises(ValueError, match="Conflicting"), transaction.atomic():
        migrate_values(apps, None)
    rule.refresh_from_db()
    assert rule.parameters == {"max_amount_irr": 1, "max_amount": new_value}
