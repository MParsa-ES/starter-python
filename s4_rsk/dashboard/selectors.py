"""Read-only database queries for the dashboard.

This is the ONLY module of the dashboard that touches database tables.
Everything else (service, view) stays independent of the models.
"""

from datetime import datetime


def count_decisions_by_type(start: datetime, end: datetime) -> dict[str, int]:
    """Count initial assessment decisions with start <= evaluated_at < end.

    Returns e.g. {"APPROVE": 12, "REJECT": 1}. A decision type with no rows may be missing.
    """
    raise NotImplementedError("Part B: needs the RiskAssessment model (US-01A).")


def count_open_review_items() -> int:
    """Count manual-review items that are still open right now."""
    raise NotImplementedError("Part B: needs the ManualReviewItem model (US-04A).")
