from django.urls import path

from dashboard.views import RiskStatisticsView

urlpatterns = [
    path("risk-statistics", RiskStatisticsView.as_view(), name="risk-statistics"),
]
