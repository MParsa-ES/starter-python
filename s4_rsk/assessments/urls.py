from django.urls import path

from assessments.history_views import (
    DecisionEventSearchView,
    TransactionDecisionHistoryView,
)
from assessments.views import (
    DecisionExplanationView,
    RiskAssessmentCreateAPIView,
    RiskAssessmentDetailAPIView,
)

urlpatterns = [
    path(
        "risk-assessments",
        RiskAssessmentCreateAPIView.as_view(),
        name="risk-assessment-create",
    ),
    path(
        "risk-assessments/<uuid:decision_id>",
        RiskAssessmentDetailAPIView.as_view(),
        name="risk-assessment-detail",
    ),
    path(
        "risk-assessments/<uuid:decision_id>/reasons",
        DecisionExplanationView.as_view(),
        name="decision-explanations",
    ),
    path(
        "transactions/<uuid:transaction_id>/decisions",
        TransactionDecisionHistoryView.as_view(),
        name="transaction-decision-history",
    ),
    path(
        "decision-events",
        DecisionEventSearchView.as_view(),
        name="decision-event-search",
    ),
]
