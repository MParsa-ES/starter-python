from uuid import UUID

from django.http import Http404

from assessments.models import RiskAssessment


def get_assessment_by_decision_id(*, decision_id: UUID) -> RiskAssessment:
    """
    Retrieves a RiskAssessment with its reasons in a single query,
    or raises Http404 (converted to RFC 9457 404 NOT_FOUND by common/exceptions.py).
    """
    try:
        return RiskAssessment.objects.prefetch_related("reasons").get(
            decision_id=decision_id
        )
    except RiskAssessment.DoesNotExist as exc:
        raise Http404(f"Risk assessment with decision_id '{decision_id}' was not found.") from exc