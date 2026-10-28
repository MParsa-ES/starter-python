from rest_framework import serializers

from .models import RiskRule


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
