import hashlib
import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import LabBankAPIException
from common.pagination import LabBankCursorPagination
from common.permissions import IsRiskOperator
from common.schema import CORRELATION_HEADERS
from common.serializers import ProblemSerializer

from .models import ManualReviewItem, ReviewActionRequest, ReviewState
from .selectors import list_review_items
from .serializers import ReviewDecisionInputSerializer, ReviewItemSerializer
from .services import claim_review_item, decide_review_item


class ReviewQueuePagination(LabBankCursorPagination):
    ordering = ("-created_at", "-item_id")


def _parse_state_filter(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    if raw_value in ReviewState.values:
        return raw_value
    raise serializers.ValidationError({"state": f"Must be one of {', '.join(ReviewState.values)}."})


def _parse_idempotency_key(request: Request) -> uuid.UUID | None:
    raw_key = request.headers.get("Idempotency-Key")
    if raw_key is None:
        return None
    try:
        return uuid.UUID(raw_key)
    except (ValueError, AttributeError) as exc:
        raise serializers.ValidationError({"Idempotency-Key": "Must be a UUID."}) from exc


def _action_fingerprint(*, action: str, item_id: uuid.UUID, body) -> str:
    canonical = {"action": action, "item_id": str(item_id), "body": body}
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), cls=DjangoJSONEncoder).encode("utf-8")
    ).hexdigest()


class ManualReviewQueueListView(ListAPIView):
    """GET /api/v1/manual-review-queue"""

    serializer_class = ReviewItemSerializer
    permission_classes = (IsAuthenticated, IsRiskOperator)
    pagination_class = ReviewQueuePagination

    def get_queryset(self):
        state = _parse_state_filter(self.request.query_params.get("state"))
        return list_review_items(state=state)

    @extend_schema(
        operation_id="listManualReviewQueue",
        summary="List transactions waiting for a human decision",
        parameters=[
            *CORRELATION_HEADERS,
            OpenApiParameter(
                name="state",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=list(ReviewState.values),
                description="Filter queue items by state (OPEN, CLAIMED, DECIDED).",
            ),
        ],
        responses={
            200: ReviewItemSerializer(many=True),
            (400, "application/problem+json"): ProblemSerializer,
            (401, "application/problem+json"): ProblemSerializer,
            (403, "application/problem+json"): ProblemSerializer,
        },
        tags=["Manual Review"],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class ManualReviewClaimView(APIView):
    """POST /api/v1/manual-review-queue/{item_id}/claim"""

    permission_classes = (IsAuthenticated, IsRiskOperator)

    @extend_schema(
        operation_id="claimReviewItem",
        summary="Claim a queue item atomically",
        parameters=[
            *CORRELATION_HEADERS,
            OpenApiParameter(
                name="Idempotency-Key",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.HEADER,
                required=False,
                description="UUID for safe POST retries.",
            ),
        ],
        request=None,
        responses={
            200: ReviewItemSerializer,
            (400, "application/problem+json"): ProblemSerializer,
            (401, "application/problem+json"): ProblemSerializer,
            (403, "application/problem+json"): ProblemSerializer,
            (404, "application/problem+json"): ProblemSerializer,
            (409, "application/problem+json"): ProblemSerializer,
        },
        tags=["Manual Review"],
    )
    def post(self, request: Request, item_id: uuid.UUID) -> Response:
        idempotency_key = _parse_idempotency_key(request)
        fingerprint = _action_fingerprint(action="claim", item_id=item_id, body=None)

        with transaction.atomic():
            record: ReviewActionRequest | None = None
            if idempotency_key is not None:
                record, created = ReviewActionRequest.objects.get_or_create(
                    key=idempotency_key,
                    defaults={"actor": request.user, "fingerprint": fingerprint},
                )
                if not created:
                    record = ReviewActionRequest.objects.select_for_update().get(pk=record.pk)
                    if record.actor_id != request.user.pk or record.fingerprint != fingerprint:
                        raise LabBankAPIException(
                            code="IDEMPOTENCY_KEY_REUSED",
                            title="Conflict",
                            detail="Idempotency key already used with a different request or caller.",
                            status_code=status.HTTP_409_CONFLICT,
                            type_slug="conflict",
                        )
                    return Response(record.response, status=status.HTTP_200_OK)

            try:
                item = claim_review_item(actor=request.user, item_id=item_id)
            except ManualReviewItem.DoesNotExist as exc:
                raise Http404(f"Manual review item '{item_id}' was not found.") from exc

            data = dict(ReviewItemSerializer(item).data)
            if record is not None:
                record.response = data
                record.save(update_fields=["response"])

            return Response(data, status=status.HTTP_200_OK)


class ManualReviewDecisionView(APIView):
    """POST /api/v1/manual-review-queue/{item_id}/decision"""

    permission_classes = (IsAuthenticated, IsRiskOperator)

    @extend_schema(
        operation_id="decideReviewItem",
        summary="Final human decision on a claimed item",
        parameters=[
            *CORRELATION_HEADERS,
            OpenApiParameter(
                name="Idempotency-Key",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.HEADER,
                required=False,
                description="UUID for safe POST retries.",
            ),
        ],
        request=ReviewDecisionInputSerializer,
        responses={
            200: ReviewItemSerializer,
            (400, "application/problem+json"): ProblemSerializer,
            (401, "application/problem+json"): ProblemSerializer,
            (403, "application/problem+json"): ProblemSerializer,
            (404, "application/problem+json"): ProblemSerializer,
            (409, "application/problem+json"): ProblemSerializer,
        },
        tags=["Manual Review"],
    )
    def post(self, request: Request, item_id: uuid.UUID) -> Response:
        idempotency_key = _parse_idempotency_key(request)
        fingerprint = _action_fingerprint(action="decision", item_id=item_id, body=request.data)

        with transaction.atomic():
            record: ReviewActionRequest | None = None
            if idempotency_key is not None:
                record, created = ReviewActionRequest.objects.get_or_create(
                    key=idempotency_key,
                    defaults={"actor": request.user, "fingerprint": fingerprint},
                )
                if not created:
                    record = ReviewActionRequest.objects.select_for_update().get(pk=record.pk)
                    if record.actor_id != request.user.pk or record.fingerprint != fingerprint:
                        raise LabBankAPIException(
                            code="IDEMPOTENCY_KEY_REUSED",
                            title="Conflict",
                            detail="Idempotency key already used with a different request or caller.",
                            status_code=status.HTTP_409_CONFLICT,
                            type_slug="conflict",
                        )
                    return Response(record.response, status=status.HTTP_200_OK)

            serializer = ReviewDecisionInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            try:
                item = decide_review_item(
                    actor=request.user,
                    item_id=item_id,
                    decision=serializer.validated_data["decision"],
                    reason=serializer.validated_data["reason"],
                )
            except ManualReviewItem.DoesNotExist as exc:
                raise Http404(f"Manual review item '{item_id}' was not found.") from exc

            data = dict(ReviewItemSerializer(item).data)
            if record is not None:
                record.response = data
                record.save(update_fields=["response"])

            return Response(data, status=status.HTTP_200_OK)
