from datetime import UTC

from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from assessments.models import DecisionEvent, DecisionType


class DecisionEventSerializer(serializers.ModelSerializer):

    decision_id = serializers.UUIDField(source="assessment_id", read_only=True)
    decision = serializers.ChoiceField(choices=DecisionType.values, read_only=True)

    class Meta:
        model = DecisionEvent
        fields = (
            "event_id",
            "decision_id",
            "transaction_id",
            "event_type",
            "decision",
            "actor",
            "reason_code",
            "reason_message",
            "created_at",
        )
        read_only_fields = fields


class DecisionEventSearchQuerySerializer(serializers.Serializer):
    """Validates optional query parameters for GET /api/v1/decision-events"""

    decision = serializers.ChoiceField(choices=DecisionType.values, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from"] = serializers.DateTimeField(required=False)
        self.fields["to"] = serializers.DateTimeField(required=False)

    def _normalize_utc(self, field_name: str, value):
        raw_value = self.initial_data.get(field_name)
        if isinstance(raw_value, str):
            parsed = parse_datetime(raw_value)
            if parsed is not None and (parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None):
                raise serializers.ValidationError(
                    {field_name: f"{field_name} must include explicit timezone information (e.g., 'Z' or '+00:00')."}
                )
        return value.astimezone(UTC)

    def validate(self, attrs: dict) -> dict:
        from_dt = attrs.get("from")
        to_dt = attrs.get("to")

        if from_dt is not None:
            attrs["from"] = self._normalize_utc("from", from_dt)
        if to_dt is not None:
            attrs["to"] = self._normalize_utc("to", to_dt)

        if attrs.get("from") is not None and attrs.get("to") is not None and attrs["from"] > attrs["to"]:
            raise serializers.ValidationError({"from": "from must not be later than to."})

        return attrs
