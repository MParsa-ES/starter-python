import pytest
from django.core.exceptions import ValidationError

from .validators import validate_rule_parameters


@pytest.mark.parametrize("amount", [1, 2**63 - 1])
def test_valid_boundaries(amount):
    validate_rule_parameters("AMOUNT_LIMIT", {"max_amount": amount})


@pytest.mark.parametrize("parameters", [None, [], {}, {"max_amount": 0},
                                       {"max_amount": True}, {"max_amount": 2**63}])
def test_invalid_validator_input(parameters):
    with pytest.raises(ValidationError):
        validate_rule_parameters("AMOUNT_LIMIT", parameters)


def test_blocklist_accepts_empty_object():
    validate_rule_parameters("BLOCKLIST", {})


@pytest.mark.parametrize("parameters", [{"max_amount_irr": 1}, {"max_amount": 1, "max_amount_irr": 1}])
def test_old_field_name_is_rejected(parameters):
    with pytest.raises(ValidationError):
        validate_rule_parameters("AMOUNT_LIMIT", parameters)


@pytest.mark.parametrize("field", ["max_daily_amount", "max_daily_count"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5, 2**63, None])
def test_invalid_daily_limits_are_rejected(field, value):
    with pytest.raises(ValidationError):
        validate_rule_parameters("AMOUNT_LIMIT", {"max_amount": 1, field: value})


@pytest.mark.parametrize("rule_type,parameters", [
    ("AMOUNT_LIMIT", {"max_amount": 1, "decision": "APPROVE"}),
    ("BLOCKLIST", {"decision": "invalid"}),
])
def test_invalid_rule_decisions_are_rejected(rule_type, parameters):
    with pytest.raises(ValidationError):
        validate_rule_parameters(rule_type, parameters)
