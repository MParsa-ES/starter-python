from django.core.exceptions import ValidationError


def validate_rule_parameters(rule_type, parameters):
    """Validate the currently agreed parameter structure for a new rule revision."""
    if not isinstance(parameters, dict):
        raise ValidationError({"parameters": "Parameters must be a JSON object."})
    if rule_type == "AMOUNT_LIMIT":
        amount = parameters.get("max_amount_irr")
        if isinstance(amount, bool) or not isinstance(amount, int) or not 1 <= amount <= 2**63 - 1:
            raise ValidationError({"parameters": "max_amount_irr must be a positive signed 64-bit integer."})
