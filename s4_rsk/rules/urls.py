from django.urls import path

from .views import RiskRuleAuditView, RiskRuleListView, RiskRuleUpdateView

urlpatterns = [
    path("risk-rules", RiskRuleListView.as_view(), name="risk-rule-list"),
    path("risk-rules/<uuid:rule_id>", RiskRuleUpdateView.as_view(), name="risk-rule-update"),
    path("risk-rules/<uuid:rule_id>/audit", RiskRuleAuditView.as_view(), name="risk-rule-audit"),
]
