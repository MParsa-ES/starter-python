"""Read-only database queries for the dashboard.

This is the ONLY module of the dashboard that touches database tables.
Everything else (service, view) stays independent of the models.
"""

from datetime import datetime

from django.db.models import Count

from assessments.models import RiskAssessment


def count_decisions_by_type(start: datetime, end: datetime) -> dict[str, int]:
    """Count initial assessment decisions with start <= evaluated_at < end.

    Returns e.g. {"APPROVE": 12, "REJECT": 1}. A decision type with no rows may be missing.
    """
    qs = RiskAssessment.objects.filter(
        evaluated_at__gte=start,
        evaluated_at__lt=end
    ).values('decision').annotate(count=Count('decision'))

    return {item['decision']: item['count'] for item in qs}

def count_open_review_items() -> int:
    """Count manual-review items that are still open right now."""
    # TODO (US-04A): Connect to ManualReviewItem once it's merged into main by Parsa.
    # Currently returning 0 so the dashboard API doesn't crash while we wait for his task.
    return 0
