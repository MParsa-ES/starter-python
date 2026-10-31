from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from assessments.selectors import get_assessment_by_decision_id
from assessments.serializers import (
    RiskAssessmentDetailResponseSerializer,
    RiskAssessmentRequestSerializer,
    RiskAssessmentResponseSerializer,
)
from assessments.services import evaluate_and_persist_assessment


class RiskAssessmentCreateAPIView(APIView):
    """
    POST /api/v1/risk-assessments
    Evaluates a payment transaction and persists the initial risk decision (US-01A).
    """

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
            400: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
        },
        tags=["Risk Assessments"],
    )
    def post(self, request: Request) -> Response:
        input_serializer = RiskAssessmentRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        assessment = evaluate_and_persist_assessment(
            **input_serializer.validated_data
        )

        output_serializer = RiskAssessmentResponseSerializer(assessment)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class RiskAssessmentDetailAPIView(APIView):
    """
    GET /api/v1/risk-assessments/{decision_id}
    Retrieves a previously evaluated risk assessment and its reasons (US-01A).
    """

    @extend_schema(
        operation_id="getRiskAssessmentById",
        summary="Retrieve a risk assessment decision by decision_id",
        responses={
            200: RiskAssessmentDetailResponseSerializer,
            404: OpenApiTypes.OBJECT,
        },
        tags=["Risk Assessments"],
    )
    def get(self, request: Request, decision_id) -> Response:
        assessment = get_assessment_by_decision_id(decision_id=decision_id)
        output_serializer = RiskAssessmentDetailResponseSerializer(assessment)
        return Response(output_serializer.data, status=status.HTTP_200_OK)
