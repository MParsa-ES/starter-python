import pytest
from django.core.exceptions import ValidationError

from .validators import validate_rule_parameters


@pytest.mark.parametrize("amount", [1, 2**63 - 1])
def test_valid_boundaries(amount):
    validate_rule_parameters("AMOUNT_LIMIT", {"max_amount_irr": amount})


@pytest.mark.parametrize("parameters", [None, [], {}, {"max_amount_irr": 0},
                                       {"max_amount_irr": True}, {"max_amount_irr": 2**63}])
def test_invalid_validator_input(parameters):
    with pytest.raises(ValidationError):
        validate_rule_parameters("AMOUNT_LIMIT", parameters)


def test_blocklist_accepts_empty_object():
    validate_rule_parameters("BLOCKLIST", {})
