from datetime import datetime

from django.db.models import Count

from assessments.models import RiskAssessment


def count_decisions_by_type(start: datetime, end: datetime) -> dict[str, int]:
    qs = RiskAssessment.objects.filter(
        evaluated_at__gte=start,
        evaluated_at__lt=end
    ).values('decision').annotate(count=Count('decision'))

    return {item['decision']: item['count'] for item in qs}

def count_open_review_items() -> int:
    # TODO (US-04A): Connect to ManualReviewItem once it's merged into main by Parsa.
    return 0
