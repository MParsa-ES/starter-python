from django.conf import settings
from django.db import models
from uuid6 import uuid7


class BlockedIdentifier(models.Model):

    class Kind(models.TextChoices):
        IBAN = "IBAN", "Iranian IBAN"

    id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
        help_text="Public UUIDv7 identifier for this blocklist entry.",
    )
    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.IBAN,
    )
    value = models.CharField(
        max_length=26,
        db_index=True,
        help_text="Blocked Iranian IBAN (IR followed by 24 digits).",
    )
    reason = models.CharField(
        max_length=255,
        help_text="Reason for blocking this identifier.",
    )
    active = models.BooleanField(
        default=True,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="blocked_identifiers_created",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="blocked_identifiers_deactivated",
    )

    class Meta:
        db_table = "rsk_blocked_identifiers"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "value"],
                condition=models.Q(active=True),
                name="uq_rsk_blocked_identifier_active_kind_value",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["IBAN"]),
                name="chk_rsk_blocked_identifier_known_kind",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="chk_rsk_blocked_identifier_reason_non_empty",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(active=True, deactivated_at__isnull=True)
                    | models.Q(active=False, deactivated_at__isnull=False)
                ),
                name="chk_rsk_blocked_identifier_active_deactivated_consistency",
            ),
        ]
        indexes = [
            models.Index(fields=["-created_at", "-id"], name="idx_rsk_blocked_id_cursor"),
            models.Index(fields=["active", "value"], name="idx_rsk_blocked_id_active_val"),
        ]

    def __str__(self) -> str:
        state = "active" if self.active else "inactive"
        return f"{self.kind}:{self.value} ({state})"


class BlockedIdentifierCreateRequest(models.Model):
    """Persist a successful response for safe POST retries (GEN-07)"""

    key = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    response = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rsk_blocked_identifier_create_requests"

    def __str__(self) -> str:
        return f"BlockedIdentifierIdempotency({self.key})"
