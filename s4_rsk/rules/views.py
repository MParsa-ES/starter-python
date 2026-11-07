import hashlib
import json
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exceptions import LabBankAPIException
from common.pagination import LabBankCursorPagination
from common.permissions import IsRiskManager
from common.schema import CORRELATION_HEADERS
from common.serializers import ProblemSerializer

from .models import RiskRule, RuleCreateRequest
from .selectors import list_risk_rules
from .serializers import RiskRuleInputSerializer, RiskRulePatchSerializer, RiskRuleSerializer, RuleRevisionSerializer
from .services import create_rule, update_rule


def _validation_error(exc):
    raise serializers.ValidationError(getattr(exc, "message_dict", exc.messages)) from exc


class RiskRuleListView(ListAPIView):
    serializer_class = RiskRuleSerializer
    permission_classes = (IsAuthenticated, IsRiskManager)

    def get_queryset(self):
        return list_risk_rules()

    @extend_schema(
        operation_id="risk_rules_list",
        parameters=CORRELATION_HEADERS,
        responses={
            200: RiskRuleSerializer(many=True),
            (403, "application/problem+json"): ProblemSerializer,
            (404, "application/problem+json"): ProblemSerializer,
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="createRiskRule",
        request=RiskRuleInputSerializer,
        parameters=[
            OpenApiParameter(
                "Idempotency-Key", str, OpenApiParameter.HEADER, required=False, description="UUID for safe retries"
            )
        ],
        responses={201: RiskRuleSerializer, 400: ProblemSerializer, 409: ProblemSerializer},
    )
    def post(self, request):
        key = request.headers.get("Idempotency-Key")
        if key is not None:
            try:
                key = uuid.UUID(key)
            except (ValueError, AttributeError):
                raise serializers.ValidationError({"Idempotency-Key": "Must be a UUID."})
        fingerprint = hashlib.sha256(
            json.dumps(request.data, sort_keys=True, separators=(",", ":"), cls=DjangoJSONEncoder).encode()
        ).hexdigest()
        try:
            with transaction.atomic():
                record = None
                if key is not None:
                    record, created = RuleCreateRequest.objects.get_or_create(
                        key=key, defaults={"actor": request.user, "fingerprint": fingerprint}
                    )
                    if not created:
                        if record.actor_id != request.user.pk or record.fingerprint != fingerprint:
                            raise LabBankAPIException(
                                "IDEMPOTENCY_KEY_REUSED", "Conflict", "Idempotency key already used.", 409, "conflict"
                            )
                        return Response(record.response, status=status.HTTP_201_CREATED)
                serializer = RiskRuleInputSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                rule = create_rule(actor=request.user, **serializer.validated_data)
                data = dict(RiskRuleSerializer(rule).data)
                if record is not None:
                    record.response = data
                    record.save(update_fields=["response"])
                return Response(data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            _validation_error(exc)


class RiskRuleUpdateView(APIView):
    permission_classes = (IsAuthenticated, IsRiskManager)

    @extend_schema(
        operation_id="updateRiskRule",
        request=RiskRulePatchSerializer,
        responses={200: RiskRuleSerializer, 400: ProblemSerializer, 404: ProblemSerializer, 409: ProblemSerializer},
    )
    def patch(self, request, rule_id):
        serializer = RiskRulePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        revision = values.pop("expected_revision")
        try:
            rule = update_rule(actor=request.user, rule_id=rule_id, expected_revision=revision, changes=values)
        except RiskRule.DoesNotExist:
            get_object_or_404(RiskRule, pk=rule_id)
        except DjangoValidationError as exc:
            _validation_error(exc)
        return Response(RiskRuleSerializer(rule).data)


class AuditPagination(LabBankCursorPagination):
    ordering = ("-revision", "-id")


class RiskRuleAuditView(ListAPIView):
    permission_classes = (IsAuthenticated, IsRiskManager)
    serializer_class = RuleRevisionSerializer
    pagination_class = AuditPagination

    def get_queryset(self):
        rule = get_object_or_404(RiskRule, pk=self.kwargs["rule_id"])
        return rule.history.select_related("actor").all()

    @extend_schema(
        operation_id="listRiskRuleAudit", responses={200: RuleRevisionSerializer(many=True), 404: ProblemSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
