from rest_framework import serializers

from common.validators import validate_iranian_iban

from .models import BlockedIdentifier


class BlockedIdentifierSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = BlockedIdentifier
        fields = (
            "id",
            "kind",
            "value",
            "reason",
            "active",
            "created_by",
            "created_at",
            "deactivated_at",
        )
        read_only_fields = fields


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Unexpected field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class BlockedIdentifierInputSerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=BlockedIdentifier.Kind.choices)
    value = serializers.CharField(max_length=26, trim_whitespace=False, validators=[validate_iranian_iban])
    reason = serializers.CharField(min_length=1, max_length=255)

    def validate_value(self, value: str) -> str:
        if not isinstance(self.initial_data.get("value"), str):
            raise serializers.ValidationError("IBAN must be a string.")
        return validate_iranian_iban(value)

    def validate_reason(self, value: str) -> str:
        if not isinstance(self.initial_data.get("reason"), str):
            raise serializers.ValidationError("Reason must be a string.")
        return value
