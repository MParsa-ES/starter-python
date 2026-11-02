
from django.urls import path

from .views import RiskRuleListView

urlpatterns = [
    path("risk-rules", RiskRuleListView.as_view(), name="risk-rule-list"),
]
