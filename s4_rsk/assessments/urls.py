from django.urls import path

from assessments.views import (
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
]