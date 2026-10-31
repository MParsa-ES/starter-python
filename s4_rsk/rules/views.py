from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from common.permissions import IsRiskManager
from common.schema import CORRELATION_HEADERS
from common.serializers import ProblemSerializer

from .selectors import list_risk_rules
from .serializers import RiskRuleSerializer


class RiskRuleListView(ListAPIView):
    serializer_class = RiskRuleSerializer
    permission_classes = (IsAuthenticated, IsRiskManager)

    def get_queryset(self):
        return list_risk_rules()

    @extend_schema(
        operation_id="risk_rules_list",
        description="List stored rule configuration, including disabled and future rules. Requires the manager group;"
                    " this endpoint does not evaluate rules.",
        parameters=CORRELATION_HEADERS,
        responses={
            200: RiskRuleSerializer(many=True),
            (403, "application/problem+json"): ProblemSerializer,
            (404, "application/problem+json"): ProblemSerializer,
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
