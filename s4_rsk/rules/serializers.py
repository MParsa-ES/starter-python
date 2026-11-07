from rest_framework import serializers

from .models import RiskRule, RuleRevision


class RiskRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskRule
        fields = (
            "id",
            "name",
            "type",
            "parameters",
            "enabled",
            "effective_at",
            "revision",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({key: "Unexpected field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class RiskRuleInputSerializer(StrictSerializer):
    name = serializers.CharField(max_length=120)
    type = serializers.ChoiceField(choices=RiskRule.Type.choices)
    parameters = serializers.DictField(allow_empty=True)
    enabled = serializers.BooleanField(required=False)
    effective_at = serializers.DateTimeField(required=False)


class RiskRulePatchSerializer(StrictSerializer):
    expected_revision = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=120, required=False)
    parameters = serializers.DictField(allow_empty=True, required=False)
    enabled = serializers.BooleanField(required=False)
    effective_at = serializers.DateTimeField(required=False)

    def validate_expected_revision(self, value):
        if isinstance(self.initial_data.get("expected_revision"), bool):
            raise serializers.ValidationError("Must be a positive integer.")
        return value

    def validate(self, attrs):
        if len(attrs) == 1:
            raise serializers.ValidationError("At least one editable field is required.")
        return attrs


class RuleRevisionSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor_id", read_only=True)

    class Meta:
        model = RuleRevision
        fields = ("revision", "actor", "changed_at", "before", "after")
        read_only_fields = fields
