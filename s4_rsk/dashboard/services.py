from datetime import datetime

from dashboard import selectors

DECISION_TYPES = ("APPROVE", "REVIEW", "REJECT")


def build_statistics(start: datetime, end: datetime) -> dict:
    """Assemble the dashboard numbers for the half-open range [start, end)."""
    counted = selectors.count_decisions_by_type(start, end)
    return {
        "start": start,
        "end": end,
        "decisions": {decision: counted.get(decision, 0) for decision in DECISION_TYPES},
        "queue_size_now": selectors.count_open_review_items(),
    }
