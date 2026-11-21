from datetime import datetime

from django.utils import timezone

from .models import RiskRule


def list_risk_rules():
    """Configuration includes disabled and future rules, not just active rules."""
    return RiskRule.objects.all().order_by("-created_at", "-id")

def list_active_rules(*, as_of: datetime | None = None):
    """Return enabled rules effective at or before `as_of` in deterministic order."""
    cutoff = as_of or timezone.now()
    return RiskRule.objects.filter(
        enabled=True,
        effective_at__lte=cutoff,
    ).order_by("created_at", "id")
