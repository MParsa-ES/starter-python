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
