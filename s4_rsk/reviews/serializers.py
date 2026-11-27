from rest_framework import serializers

from assessments.models import DecisionType

from .models import ManualReviewItem


class ReviewItemSerializer(serializers.ModelSerializer):
    decision_id = serializers.UUIDField(source="assessment_id", read_only=True)
    claimed_by = serializers.CharField(source="claimed_by.username", allow_null=True, read_only=True)

    class Meta:
        model = ManualReviewItem
        fields = (
            "item_id",
            "decision_id",
            "transaction_id",
            "state",
            "claimed_by",
            "created_at",
        )
        read_only_fields = fields


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Unexpected field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class ReviewDecisionInputSerializer(StrictSerializer):
    decision = serializers.ChoiceField(choices=(DecisionType.APPROVE, DecisionType.REJECT))
    reason = serializers.CharField(min_length=1, max_length=255)

    def validate_reason(self, value: str) -> str:
        if not isinstance(self.initial_data.get("reason"), str):
            raise serializers.ValidationError("Reason must be a string.")
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("A non-empty reason is required.")
        return cleaned
