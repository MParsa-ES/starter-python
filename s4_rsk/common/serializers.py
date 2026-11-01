from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["UP"])
    service = serializers.CharField()


class ReadySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["READY"])
    service = serializers.CharField()
    database = serializers.ChoiceField(choices=["CONNECTED"])


class ProblemSerializer(serializers.Serializer):
    type = serializers.URLField()
    title = serializers.CharField()
    status = serializers.IntegerField()
    code = serializers.CharField()
    detail = serializers.CharField()
    correlation_id = serializers.CharField()
