from typing import ClassVar

from django.db import models
from django.utils import timezone
from uuid6 import uuid7


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
