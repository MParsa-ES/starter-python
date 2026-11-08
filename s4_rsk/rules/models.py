from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone
from uuid6 import uuid7

from .validators import validate_rule_parameters


class RiskRule(models.Model):
    class Type(models.TextChoices):
        AMOUNT_LIMIT = "AMOUNT_LIMIT", "Amount limit"
        BLOCKLIST = "BLOCKLIST", "Blocklist"

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=32, choices=Type.choices)
    parameters = models.JSONField(default=dict)
    enabled = models.BooleanField(default=False)
    effective_at = models.DateTimeField(default=timezone.now)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering: ClassVar = ["-created_at", "-id"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=models.Q(type__in=["AMOUNT_LIMIT", "BLOCKLIST"]),
                name="risk_rule_known_type",
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gte=1),
                name="risk_rule_revision_positive",
            ),
        ]

    def __str__(self):
        return f"{self.name} (revision {self.revision})"

    def clean(self):
        super().clean()
        validate_rule_parameters(self.type, self.parameters)


class RuleRevision(models.Model):
    """A recorded before/after state for an explicit rule management operation."""

    rule = models.ForeignKey(RiskRule, on_delete=models.PROTECT, related_name="history")
    revision = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField()

    class Meta:
        ordering: ClassVar = ["-revision"]
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["rule", "revision"], name="unique_rule_revision"),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name="rule_history_revision_positive"),
        ]


class RuleCreateRequest(models.Model):
    """Persist a successful response for safe POST retries."""

    key = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    response = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
