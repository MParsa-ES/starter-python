from .models import RiskRule


def list_risk_rules():
    """Configuration includes disabled and future rules, not just active rules."""
    return RiskRule.objects.all().order_by("-created_at", "-id")
