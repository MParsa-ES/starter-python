from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from assessments.history_selectors import list_transaction_decision_events, search_decision_events
from assessments.history_serializers import DecisionEventSearchQuerySerializer, DecisionEventSerializer
from assessments.models import DecisionEvent, DecisionType
from common.pagination import LabBankCursorPagination
from common.permissions import CanReadDecisionHistory
from common.schema import CORRELATION_HEADERS
from common.serializers import ProblemSerializer


class TransactionDecisionPagination(LabBankCursorPagination):
    """Cursor pagination ordered oldest-first for a single transaction's decision timeline."""

    ordering = ("created_at", "event_id")


class DecisionEventSearchPagination(LabBankCursorPagination):
    """Cursor pagination ordered newest-first for bounded decision event search."""

    ordering = ("-created_at", "-event_id")


class TransactionDecisionHistoryView(ListAPIView):
    """
    GET /api/v1/transactions/{transaction_id}/decisions
    Returns the append-only decision timeline of a transaction, oldest first (US-06).
    """

    permission_classes = (IsAuthenticated, CanReadDecisionHistory)
    serializer_class = DecisionEventSerializer
    pagination_class = TransactionDecisionPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DecisionEvent.objects.none()
        return list_transaction_decision_events(transaction_id=self.kwargs["transaction_id"])

    @extend_schema(
        operation_id="listTransactionDecisions",
        summary="Append-only decision history of one transaction",
        parameters=CORRELATION_HEADERS,
        responses={
            200: DecisionEventSerializer(many=True),
            (400, "application/problem+json"): ProblemSerializer,
            (401, "application/problem+json"): ProblemSerializer,
            (403, "application/problem+json"): ProblemSerializer,
            (404, "application/problem+json"): ProblemSerializer,
        },
        tags=["Risk Assessments"],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class DecisionEventSearchView(ListAPIView):
    """
    GET /api/v1/decision-events
    Bounded search over decision events with optional decision and [from, to) UTC filters (US-06).
    """

    permission_classes = (IsAuthenticated, CanReadDecisionHistory)
    serializer_class = DecisionEventSerializer
    pagination_class = DecisionEventSearchPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DecisionEvent.objects.none()

        query = DecisionEventSearchQuerySerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        validated = query.validated_data

        return search_decision_events(
            decision=validated.get("decision"),
            from_dt=validated.get("from"),
            to_dt=validated.get("to"),
        )

    @extend_schema(
        operation_id="searchDecisionEvents",
        summary="Bounded search over decision events",
        parameters=[
            *CORRELATION_HEADERS,
            OpenApiParameter(
                name="decision",
                type=OpenApiTypes.STR,
                enum=list(DecisionType.values),
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by decision outcome (APPROVE, REVIEW, REJECT).",
            ),
            OpenApiParameter(
                name="from",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Inclusive lower bound, ISO 8601 UTC.",
            ),
            OpenApiParameter(
                name="to",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Exclusive upper bound, ISO 8601 UTC.",
            ),
        ],
        responses={
            200: DecisionEventSerializer(many=True),
            (400, "application/problem+json"): ProblemSerializer,
            (401, "application/problem+json"): ProblemSerializer,
            (403, "application/problem+json"): ProblemSerializer,
        },
        tags=["Risk Assessments"],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)
