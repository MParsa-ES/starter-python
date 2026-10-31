from django.db import models
from uuid6 import uuid7


class DecisionType(models.TextChoices):
    APPROVE = "APPROVE", "Approve"
    REJECT = "REJECT", "Reject"
    REVIEW = "REVIEW", "Review"


class EventType(models.TextChoices):
    INITIAL_EVALUATION = "INITIAL_EVALUATION", "Initial Automated Evaluation"
    MANUAL_DECISION = "MANUAL_DECISION", "Manual Operator Decision"


class RiskAssessment(models.Model):
    """
    Immutable record of an initial transaction risk assessment
    """

    decision_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
        help_text="Public UUIDv7 identifier for this assessment decision",
    )

    transaction_id = models.UUIDField(
        db_index=True, help_text="UUID of the payment transfer owned by S3-Pay"
    )

    amount = models.BigIntegerField(
        help_text="Transaction amount in IRR (positive integer)"
    )

    currency = models.CharField(max_length=3, default="IRR")

    source_iban = models.CharField(
        max_length=26,
        db_index=True,
    )

    destination_iban = models.CharField(
        max_length=26,
        db_index=True,
    )

    occurred_at = models.DateTimeField(
        help_text="Date and time at which the transaction occured in S3-Pay"
    )

    input_fingerprint = models.CharField(
        max_length=64, help_text="SHA-256 hash of the assessment request payload"
    )

    decision = models.CharField(
        max_length=10,
        choices=DecisionType.choices,
        db_index=True,
    )

    evaluated_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when S4-RSK evaluated the transaction",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Required for cursor pagination stability",
    )

    correlation_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )

    class Meta:
        db_table = "risk_assessments"
        ordering = ["-created_at", "-decision_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="chk_rsk_assessment_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IRR"),
                name="chk_rsk_assessment_currency_irr",
            ),
        ]
        indexes = [
            models.Index(
                fields=["-created_at", "-decision_id"], name="idx_rsk_assessment_cursor"
            ),
        ]

    def __str__(self):
        return f"Assessment {self.decision_id} (tx={self.transaction_id}) -> {self.decision}"


class DecisionReason(models.Model):
    """
    Stores the machine-readable code, human message, and immutable rule snapshot
    explaining why a RiskAssessment reached its decision.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )

    assessment = models.ForeignKey(
        RiskAssessment,
        on_delete=models.CASCADE,
        related_name="reasons",
    )

    code = models.CharField(
        max_length=64,
        help_text="Stable machine-readable reason code (e.g., NO_RULE_MATCHED, BLOCKED_IBAN)",
    )

    message = models.CharField(
        max_length=255,
        help_text="Human readable message explaining the reason",
    )

    rule_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID of the RiskRule that triggered this reason, if applicable",
    )

    rule_revision = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Immutable revision number of the rule at evalution time",
    )

    rule_snapshot = models.JSONField(
        null=True,
        blank=True,
        help_text="Frozen snapshot of rule parameters at the moment of evaluation",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "rsk_decision_reasons"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.code} ({self.assessment_id})"


class DecisionEvent(models.Model):
    """
    Append-only timeline of decision events for a transaction (both initial & human review)
    """

    event_id = models.UUIDField(
        primary_key=True,
        default=uuid7,
        editable=False,
    )

    assessment = models.ForeignKey(
        RiskAssessment, on_delete=models.PROTECT, related_name="events"
    )

    transaction_id = models.UUIDField(
        db_index=True,
    )

    event_type = models.CharField(
        max_length=32,
        choices=EventType.choices,
        default=EventType.INITIAL_EVALUATION,
    )

    decision = models.CharField(
        max_length=10,
        choices=DecisionType.choices,
    )

    actor = models.CharField(
        max_length=128,
        default="SYSTEM",
        help_text="SYSTEM for initial evaluation, or authenticated operator ID",
    )

    reason_code = models.CharField(max_length=64)
    reason_message = models.CharField(max_length=255)
    rule_snapshot = models.JSONField(null=True, blank=True)
    correlation_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "rsk_decision_events"
        ordering = ["created_at", "event_id"]
        indexes = [
            models.Index(
                fields=["transaction_id", "created_at", "event_id"],
                name="idx_rsk_decision_event_tx",
            ),
        ]
    def __str__(self):
        return f"Event {self.event_id} {self.event_type} -> {self.decision}"


