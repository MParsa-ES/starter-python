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
from common.permissions import IsRiskManager
from common.schema import CORRELATION_HEADERS
from common.serializers import ProblemSerializer

from .models import BlockedIdentifier, BlockedIdentifierCreateRequest
from .selectors import list_blocked_identifiers
from .serializers import BlockedIdentifierInputSerializer, BlockedIdentifierSerializer
from .services import create_blocked_identifier, deactivate_blocked_identifier


def _parse_active_filter(raw_value: str | None) -> bool | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise serializers.ValidationError({"active": "Must be a boolean ('true' or 'false')."})


class BlockedIdentifierListCreateView(ListAPIView):
    """
    GET  /api/v1/blocked-identifiers
    POST /api/v1/blocked-identifiers
    """

    serializer_class = BlockedIdentifierSerializer
    permission_classes = (IsAuthenticated, IsRiskManager)
    pagination_class = LabBankCursorPagination

    def get_queryset(self):
        active = _parse_active_filter(self.request.query_params.get("active"))
        return list_blocked_identifiers(active=active)

    @extend_schema(
        operation_id="listBlockedIdentifiers",
        summary="List blocked identifiers",
        parameters=[
            *CORRELATION_HEADERS,
            OpenApiParameter(
                name="active",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by active flag.",
            ),
        ],
        responses={
            200: BlockedIdentifierSerializer(many=True),
            (400, "application/problem+json"): ProblemSerializer,
            (401, "application/problem+json"): ProblemSerializer,
            (403, "application/problem+json"): ProblemSerializer,
        },
        tags=["Blocked Identifiers"],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        operation_id="createBlockedIdentifier",
        summary="Block an IBAN",
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
        request=BlockedIdentifierInputSerializer,
        responses={
            201: BlockedIdentifierSerializer,
            (400, "application/problem+json"): ProblemSerializer,
            (401, "application/problem+json"): ProblemSerializer,
            (403, "application/problem+json"): ProblemSerializer,
            (409, "application/problem+json"): ProblemSerializer,
        },
        tags=["Blocked Identifiers"],
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
            record: BlockedIdentifierCreateRequest | None = None
            if idempotency_key is not None:
                record, created = BlockedIdentifierCreateRequest.objects.get_or_create(
                    key=idempotency_key,
                    defaults={"actor": request.user, "fingerprint": fingerprint},
                )
                if not created:
                    record = BlockedIdentifierCreateRequest.objects.select_for_update().get(pk=record.pk)
                    if record.actor_id != request.user.pk or record.fingerprint != fingerprint:
                        raise LabBankAPIException(
                            code="IDEMPOTENCY_KEY_REUSED",
                            title="Conflict",
                            detail="Idempotency key already used with a different request payload or caller.",
                            status_code=status.HTTP_409_CONFLICT,
                            type_slug="conflict",
                        )
                    return Response(record.response, status=status.HTTP_201_CREATED)

            serializer = BlockedIdentifierInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            entry = create_blocked_identifier(actor=request.user, **serializer.validated_data)
            data = dict(BlockedIdentifierSerializer(entry).data)

            if record is not None:
                record.response = data
                record.save(update_fields=["response"])

            return Response(data, status=status.HTTP_201_CREATED)


class BlockedIdentifierDetailView(APIView):
    """
    DELETE /api/v1/blocked-identifiers/{id}
    Deactivates a blocked identifier (soft delete)
    """

    permission_classes = (IsAuthenticated, IsRiskManager)

    @extend_schema(
        operation_id="deactivateBlockedIdentifier",
        summary="Deactivate a blocked identifier (soft delete, audit is kept)",
        parameters=CORRELATION_HEADERS,
        responses={
            204: None,
            (401, "application/problem+json"): ProblemSerializer,
            (403, "application/problem+json"): ProblemSerializer,
            (404, "application/problem+json"): ProblemSerializer,
        },
        tags=["Blocked Identifiers"],
    )
    def delete(self, request: Request, identifier_id: uuid.UUID) -> Response:
        try:
            deactivate_blocked_identifier(actor=request.user, identifier_id=identifier_id)
        except BlockedIdentifier.DoesNotExist as exc:
            raise Http404("Blocked identifier not found.") from exc
        return Response(status=status.HTTP_204_NO_CONTENT)
