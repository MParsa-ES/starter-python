from rest_framework import serializers


class StatisticsQuerySerializer(serializers.Serializer):
    """Validates the query string of GET /api/v1/risk-statistics."""

    start = serializers.DateTimeField(
        help_text="Range start, inclusive. ISO 8601 in UTC, e.g. 2026-10-24T00:00:00Z"
    )
    end = serializers.DateTimeField(
        help_text="Range end, exclusive. ISO 8601 in UTC, e.g. 2026-10-25T00:00:00Z"
    )

    def validate(self, attrs):
        if attrs["start"] > attrs["end"]:
            raise serializers.ValidationError("start must not be later than end.")
        return attrs


class DecisionCountsSerializer(serializers.Serializer):
    APPROVE = serializers.IntegerField()
    REVIEW = serializers.IntegerField()
    REJECT = serializers.IntegerField()


class StatisticsResponseSerializer(serializers.Serializer):
    """Shape of the statistics response (also used to document it in Swagger)."""

    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    decisions = DecisionCountsSerializer(
        help_text="Initial assessment decisions with start <= evaluated_at < end."
    )
    queue_size_now = serializers.IntegerField(
        help_text="Open manual-review items right now. A snapshot, NOT a count for the range."
    )
