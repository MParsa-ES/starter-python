from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from common.exceptions import LabBankAPIException

from .models import RiskRule, RuleRevision
from .services import create_rule, update_rule

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager(django_user_model):
    user = django_user_model.objects.create_user("history-manager")
    user.groups.add(Group.objects.create(name="manager"))
    return user


def test_create_and_update_record_before_after_and_actor(manager):
    rule = create_rule(actor=manager, name="limit", type="AMOUNT_LIMIT", parameters={"max_amount": 100})
    created = rule.history.get(revision=1)
    assert created.before is None
    assert created.after["parameters"] == {"max_amount": 100}
    assert created.actor == manager
    assert created.changed_at is not None

    update_rule(actor=manager, rule_id=rule.pk, expected_revision=1, changes={"parameters": {"max_amount": 200}})
    rule.refresh_from_db()
    updated = rule.history.get(revision=2)
    assert rule.revision == 2
    assert updated.before["parameters"] == {"max_amount": 100}
    assert updated.before["revision"] == 1
    assert updated.after["parameters"] == {"max_amount": 200}
    assert updated.after["revision"] == 2
    assert created.after["parameters"] == {"max_amount": 100}


@pytest.mark.parametrize(
    "parameters",
    [
        {},
        {"max_amount": 0},
        {"max_amount": -1},
        {"max_amount": True},
        {"max_amount": 1.5},
        {"max_amount": 2**63},
        [],
        None,
    ],
)
def test_invalid_amount_parameters_do_not_create_rule_or_history(manager, parameters):
    with pytest.raises(ValidationError):
        create_rule(actor=manager, name="limit", type="AMOUNT_LIMIT", parameters=parameters)
    assert RiskRule.objects.count() == 0
    assert RuleRevision.objects.count() == 0


@pytest.mark.parametrize("amount", [1, 2**63 - 1])
def test_valid_amount_boundaries(manager, amount):
    rule = create_rule(actor=manager, name="limit", type="AMOUNT_LIMIT", parameters={"max_amount": amount})
    assert rule.history.count() == 1


def test_stale_revision_and_invalid_update_do_not_change_state(manager):
    rule = create_rule(actor=manager, name="limit", type="AMOUNT_LIMIT", parameters={"max_amount": 100})
    with pytest.raises(LabBankAPIException) as error:
        update_rule(actor=manager, rule_id=rule.pk, expected_revision=2, changes={"name": "changed"})
    assert error.value.status_code == 409
    with pytest.raises(ValidationError):
        update_rule(actor=manager, rule_id=rule.pk, expected_revision=1, changes={"parameters": {"max_amount": 0}})
    rule.refresh_from_db()
    assert rule.revision == 1
    assert rule.name == "limit"
    assert rule.history.count() == 1


def test_history_failure_rolls_back_rule(manager):
    with (
        patch("rules.services.RuleRevision.objects.create", side_effect=RuntimeError("failure")),
        pytest.raises(RuntimeError),
    ):
        create_rule(actor=manager, name="blocklist", type="BLOCKLIST", parameters={})
    assert not RiskRule.objects.exists()


def test_history_failure_rolls_back_existing_rule_update(manager):
    rule = create_rule(actor=manager, name="old", type="BLOCKLIST", parameters={})
    with (
        patch("rules.services.RuleRevision.objects.create", side_effect=RuntimeError("failure")),
        pytest.raises(RuntimeError),
    ):
        update_rule(actor=manager, rule_id=rule.pk, expected_revision=1, changes={"name": "new"})
    rule.refresh_from_db()
    assert (rule.name, rule.revision, rule.history.count()) == ("old", 1, 1)


def test_existing_rule_gets_history_only_when_updated(manager):
    rule = RiskRule.objects.create(name="old", type="BLOCKLIST", parameters={}, revision=3)
    assert not rule.history.exists()
    update_rule(actor=manager, rule_id=rule.pk, expected_revision=3, changes={"name": "new"})
    history = rule.history.get()
    assert history.revision == 4
    assert history.before["name"] == "old"
    assert history.after["name"] == "new"


def test_only_manager_can_write_history(django_user_model):
    user = django_user_model.objects.create_user("not-manager")
    with pytest.raises(PermissionDenied):
        create_rule(actor=user, name="blocklist", type="BLOCKLIST", parameters={})
    assert not RiskRule.objects.exists()


def test_revision_unique_per_rule(manager):
    rule = create_rule(actor=manager, name="blocklist", type="BLOCKLIST", parameters={})
    with transaction.atomic(), pytest.raises(IntegrityError):
        RuleRevision.objects.create(rule=rule, revision=1, actor=manager, after={})
