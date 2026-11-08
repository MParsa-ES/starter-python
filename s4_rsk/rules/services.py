import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from common.exceptions import LabBankAPIException

from .models import RiskRule, RuleRevision

_EDITABLE_FIELDS = frozenset({"name", "type", "parameters", "enabled", "effective_at"})


def _check_actor(actor):
    if (
        not actor
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.groups.filter(name="manager").exists()
    ):
        raise PermissionDenied("An active manager is required.")


def _snapshot(rule):
    values = {field: getattr(rule, field) for field in _EDITABLE_FIELDS}
    values.update(id=str(rule.pk), revision=rule.revision)
    return json.loads(json.dumps(values, cls=DjangoJSONEncoder))


@transaction.atomic
def create_rule(*, actor, **fields):
    _check_actor(actor)
    if set(fields) - _EDITABLE_FIELDS:
        raise ValidationError("Unexpected rule fields.")
    rule = RiskRule(**fields)
    rule.full_clean(exclude=["parameters"])
    rule.save()
    RuleRevision.objects.create(rule=rule, revision=rule.revision, actor=actor, before=None, after=_snapshot(rule))
    return rule


@transaction.atomic
def update_rule(*, actor, rule_id, expected_revision, changes):
    _check_actor(actor)
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 1:
        raise ValidationError("Expected revision must be a positive integer.")
    if not isinstance(changes, dict) or not changes or set(changes) - _EDITABLE_FIELDS:
        raise ValidationError("Supply only editable rule fields.")
    rule = RiskRule.objects.select_for_update().get(pk=rule_id)
    if rule.revision != expected_revision:
        raise LabBankAPIException("CONFLICT", "Conflict", "Rule revision is stale.", 409, "conflict")
    before = _snapshot(rule)
    for field, value in changes.items():
        setattr(rule, field, value)
    rule.revision += 1
    rule.full_clean(exclude=["parameters"])
    rule.save()
    RuleRevision.objects.create(rule=rule, revision=rule.revision, actor=actor, before=before, after=_snapshot(rule))
    return rule
