from django.conf import settings
from django.db import models
from uuid6 import uuid7

from assessments.models import RiskAssessment


class ReviewState(models.TextChoices):
    OPEN = "OPEN", "Open"
    CLAIMED = "CLAIMED", "Claimed"
    DECIDED = "DECIDED", "Decided"


class ManualReviewItem(models.Model):
    """Queue item created automatically when a RiskAssessment reaches REVIEW."""

    item_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
        help_text="Public UUIDv7 identifier for this manual review item.",
    )
    assessment = models.OneToOneField(
        RiskAssessment,
        on_delete=models.PROTECT,
        related_name="review_item",
    )
    transaction_id = models.UUIDField(
        db_index=True,
        help_text="UUID of the transfer under review (denormalized from RiskAssessment).",
    )
    state = models.CharField(
        max_length=16,
        choices=ReviewState.choices,
        default=ReviewState.OPEN,
        db_index=True,
    )
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="claimed_review_items",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "rsk_manual_review_items"
        ordering = ["-created_at", "-item_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(state__in=["OPEN", "CLAIMED", "DECIDED"]),
                name="chk_rsk_review_item_known_state",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(state="OPEN", claimed_by__isnull=True, claimed_at__isnull=True, decided_at__isnull=True)
                    | models.Q(
                        state="CLAIMED",
                        claimed_by__isnull=False,
                        claimed_at__isnull=False,
                        decided_at__isnull=True,
                    )
                    | models.Q(
                        state="DECIDED",
                        claimed_by__isnull=False,
                        claimed_at__isnull=False,
                        decided_at__isnull=False,
                    )
                ),
                name="chk_rsk_review_item_state_consistency",
            ),
        ]
        indexes = [
            models.Index(fields=["-created_at", "-item_id"], name="idx_rsk_review_item_cursor"),
            models.Index(fields=["state", "-created_at"], name="idx_rsk_review_item_state"),
        ]

    def __str__(self) -> str:
        return f"ReviewItem {self.item_id} ({self.state})"


class ReviewActionRequest(models.Model):
    """Persists successful claim/decision responses for safe POST retries (GEN-07)."""

    key = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    response = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rsk_review_action_requests"

    def __str__(self) -> str:
        return f"ReviewActionIdempotency({self.key})"
