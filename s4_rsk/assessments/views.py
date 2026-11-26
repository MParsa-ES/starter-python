import hashlib
import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from assessments.models import AssessmentCreateRequest, DecisionReason, RiskAssessment
from assessments.selectors import get_assessment_by_decision_id
from assessments.serializers import (
    DecisionExplanationSerializer,
    RiskAssessmentDetailResponseSerializer,
    RiskAssessmentRequestSerializer,
    RiskAssessmentResponseSerializer,
)
from assessments.services import evaluate_and_persist_assessment
from common.exceptions import LabBankAPIException
from common.pagination import LabBankCursorPagination
from common.permissions import CanReadDecisionHistory, IsPaymentService
from common.serializers import ProblemSerializer


class RiskAssessmentCreateAPIView(APIView):
    """
    POST /api/v1/risk-assessments
    Evaluates a payment transaction and persists the initial risk decision (US-01A / US-01B).
    """

    permission_classes = (IsAuthenticated, IsPaymentService)

    @extend_schema(
        operation_id="createRiskAssessment",
        summary="Evaluate transaction risk and persist decision",
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.HEADER,
                required=False,
                description="Unique key to guarantee idempotent assessment creation.",
            ),
            OpenApiParameter(
                name="X-Correlation-ID",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=False,
                description="Distributed tracing correlation identifier.",
            ),
        ],
        request=RiskAssessmentRequestSerializer,
        responses={
            201: RiskAssessmentResponseSerializer,
            400: ProblemSerializer,
            409: ProblemSerializer,
        },
        tags=["Risk Assessments"],
    )
    def post(self, request: Request) -> Response:
        raw_key = request.headers.get("Idempotency-Key")
        idempotency_key: uuid.UUID | None = None
        if raw_key is not None:
            try:
                idempotency_key = uuid.UUID(raw_key)
            except (ValueError, AttributeError) as exc:
                raise serializers.ValidationError({"Idempotency-Key": "Must be a UUID."}) from exc

        fingerprint = hashlib.sha256(
            json.dumps(request.data, sort_keys=True, separators=(",", ":"), cls=DjangoJSONEncoder).encode("utf-8")
        ).hexdigest()

        with transaction.atomic():
            record: AssessmentCreateRequest | None = None
            if idempotency_key is not None:
                record, created = AssessmentCreateRequest.objects.get_or_create(
                    key=idempotency_key,
                    defaults={"actor": request.user, "fingerprint": fingerprint},
                )
                if not created:
                    record = AssessmentCreateRequest.objects.select_for_update().get(pk=record.pk)
                    if record.actor_id != request.user.pk or record.fingerprint != fingerprint:
                        raise LabBankAPIException(
                            code="IDEMPOTENCY_KEY_REUSED",
                            title="Conflict",
                            detail="Idempotency key already used with a different request payload or caller.",
                            status_code=status.HTTP_409_CONFLICT,
                            type_slug="conflict",
                        )
                    return Response(record.response, status=status.HTTP_201_CREATED)

            input_serializer = RiskAssessmentRequestSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)

            assessment = evaluate_and_persist_assessment(**input_serializer.validated_data)

            data = dict(RiskAssessmentResponseSerializer(assessment).data)
            if record is not None:
                record.response = data
                record.save(update_fields=["response"])

            return Response(data, status=status.HTTP_201_CREATED)


class RiskAssessmentDetailAPIView(APIView):
    """
    GET /api/v1/risk-assessments/{decision_id}
    Retrieves a previously evaluated risk assessment and its reasons (US-01A).
    """

    permission_classes = (IsAuthenticated, IsPaymentService)

    @extend_schema(
        operation_id="getRiskAssessmentById",
        summary="Retrieve a risk assessment decision by decision_id",
        responses={
            200: RiskAssessmentDetailResponseSerializer,
            404: ProblemSerializer,
        },
        tags=["Risk Assessments"],
    )
    def get(self, request: Request, decision_id) -> Response:
        assessment = get_assessment_by_decision_id(decision_id=decision_id)
        output_serializer = RiskAssessmentDetailResponseSerializer(assessment)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class ExplanationPagination(LabBankCursorPagination):
    ordering = ("created_at", "id")


class DecisionExplanationView(ListAPIView):
    permission_classes = (IsAuthenticated, CanReadDecisionHistory)
    serializer_class = DecisionExplanationSerializer
    pagination_class = ExplanationPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DecisionReason.objects.none()
        assessment = get_object_or_404(RiskAssessment, pk=self.kwargs["decision_id"])
        return assessment.reasons.all().order_by("created_at", "id")

    @extend_schema(
        operation_id="listDecisionExplanations",
        summary="List the recorded reasons for an assessment",
        responses={200: DecisionExplanationSerializer(many=True), 401: ProblemSerializer,
                   403: ProblemSerializer, 404: ProblemSerializer},
        tags=["Risk Assessments"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
