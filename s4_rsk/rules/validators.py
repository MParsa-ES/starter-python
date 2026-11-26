from django.core.exceptions import ValidationError


def validate_rule_parameters(rule_type, parameters):
    """Validate the currently agreed parameter structure for a new rule revision."""
    if not isinstance(parameters, dict):
        raise ValidationError({"parameters": "Parameters must be a JSON object."})
    if rule_type == "AMOUNT_LIMIT":
        if "max_amount_irr" in parameters:
            raise ValidationError({"parameters": "Use max_amount; max_amount_irr is no longer accepted."})
        amount = parameters.get("max_amount")
        if isinstance(amount, bool) or not isinstance(amount, int) or not 1 <= amount <= 2**63 - 1:
            raise ValidationError({"parameters": "max_amount must be a positive signed 64-bit integer."})
        for field in ("max_daily_amount", "max_daily_count"):
            if field in parameters:
                value = parameters[field]
                if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 2**63 - 1:
                    raise ValidationError({"parameters": f"{field} must be a positive signed 64-bit integer."})
    if "decision" in parameters and parameters["decision"] not in ("REVIEW", "REJECT"):
        raise ValidationError({"parameters": "decision must be REVIEW or REJECT."})
