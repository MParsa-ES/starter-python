from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from dashboard import services
from dashboard.serializers import StatisticsQuerySerializer, StatisticsResponseSerializer


class RiskStatisticsView(APIView):
    """GET /api/v1/risk-statistics?start=...&end=... (US-03A)."""

    # TODO(ADR-005): restrict to the risk-manager role once authentication exists.
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="get_risk_statistics",
        parameters=[StatisticsQuerySerializer],
        responses=StatisticsResponseSerializer,
    )
    def get(self, request):
        query = StatisticsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)  # invalid input -> 400 Problem Details

        statistics = services.build_statistics(**query.validated_data)
        return Response(StatisticsResponseSerializer(statistics).data)
