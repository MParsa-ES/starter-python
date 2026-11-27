from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from django.apps import apps

from assessments.models import DecisionType, TransferType
from integrations.ledger_client import (
    STATUS_ACCOUNT_NOT_FOUND,
    STATUS_OK,
    LedgerHistory,
)
from rules.models import RiskRule

DEFAULT_APPROVE_CODE = "NO_RULE_MATCHED"
DEFAULT_APPROVE_MESSAGE = "No blocking rule matched"

DECISION_SEVERITY: dict[str, int] = {
    DecisionType.APPROVE: 0,
    DecisionType.REVIEW: 1,
    DecisionType.REJECT: 2,
}


@dataclass(frozen=True)
class EvaluationContext:
    """Immutable transaction and ledger inputs passed into the rule engine."""

    transaction_id: UUID
    transfer_type: str
    source_account_id: UUID
    destination_account_id: UUID | None
    destination_iban: str | None
    amount: int
    currency: str
    ledger_history: LedgerHistory | None = None

    @property
    def destination_target(self) -> str:
        if self.transfer_type == TransferType.INTERNAL:
            return str(self.destination_account_id)
        return self.destination_iban or ""


@dataclass(frozen=True)
class RuleMatch:
    """A single decision reason produced by evaluation (or default approval)."""

    code: str
    message: str
    decision: str = DecisionType.APPROVE
    rule_id: UUID | None = None
    rule_revision: int | None = None
    rule_snapshot: dict | None = None


@dataclass(frozen=True)
class EvaluationResult:
    """Aggregated engine outcome persisted by assessments.services."""

    decision: str
    reasons: tuple[RuleMatch, ...]

    @property
    def primary_reason(self) -> RuleMatch:
        return max(self.reasons, key=lambda r: DECISION_SEVERITY[r.decision])


def build_rule_snapshot(rule: RiskRule) -> dict:
    """Freeze rule state at the exact moment of evaluation."""
    return {
        "id": str(rule.id),
        "name": rule.name,
        "type": rule.type,
        "parameters": dict(rule.parameters),
        "revision": rule.revision,
        "effective_at": rule.effective_at.isoformat(),
    }


def _resolve_rule_decision(parameters: dict, *, default: str = DecisionType.REJECT) -> str:
    configured = parameters.get("decision")
    if configured in (DecisionType.REJECT, DecisionType.REVIEW):
        return configured
    return default


def _evaluate_amount_limit(ctx: EvaluationContext, rule: RiskRule) -> list[RuleMatch]:
    matches: list[RuleMatch] = []
    params = rule.parameters or {}
    decision = _resolve_rule_decision(params, default=DecisionType.REJECT)
    snapshot = build_rule_snapshot(rule)

    max_amount = params.get("max_amount")
    if not isinstance(max_amount, bool) and isinstance(max_amount, int) and ctx.amount > max_amount:
        matches.append(
            RuleMatch(
                code="AMOUNT_LIMIT_EXCEEDED",
                message=f"Transaction amount {ctx.amount} IRR exceeds limit of {max_amount} IRR ({rule.name}).",
                decision=decision,
                rule_id=rule.id,
                rule_revision=rule.revision,
                rule_snapshot=snapshot,
            )
        )

    if ctx.ledger_history is None and any(key in params for key in ("max_daily_amount", "max_daily_count")):
        matches.append(
            RuleMatch(
                code="LEDGER_UNAVAILABLE",
                message="Daily limits cannot be evaluated without ledger history.",
                decision=DecisionType.REVIEW,
                rule_id=rule.id,
                rule_revision=rule.revision,
                rule_snapshot=snapshot,
            )
        )

    if ctx.ledger_history is not None and ctx.ledger_history.status == STATUS_OK:
        prior_entries = ctx.ledger_history.entries

        max_daily_amount = params.get("max_daily_amount")
        if not isinstance(max_daily_amount, bool) and isinstance(max_daily_amount, int):
            cumulative_amount = sum(entry.amount for entry in prior_entries) + ctx.amount
            if cumulative_amount > max_daily_amount:
                matches.append(
                    RuleMatch(
                        code="DAILY_AMOUNT_LIMIT_EXCEEDED",
                        message=(
                            f"Cumulative daily debit {cumulative_amount} IRR exceeds daily limit "
                            f"of {max_daily_amount} IRR ({rule.name})."
                        ),
                        decision=decision,
                        rule_id=rule.id,
                        rule_revision=rule.revision,
                        rule_snapshot=snapshot,
                    )
                )

        max_daily_count = params.get("max_daily_count")
        if not isinstance(max_daily_count, bool) and isinstance(max_daily_count, int):
            cumulative_count = len(prior_entries) + 1
            if cumulative_count > max_daily_count:
                matches.append(
                    RuleMatch(
                        code="DAILY_VELOCITY_LIMIT_EXCEEDED",
                        message=(
                            f"Daily debit count {cumulative_count} exceeds daily limit "
                            f"of {max_daily_count} transfers ({rule.name})."
                        ),
                        decision=decision,
                        rule_id=rule.id,
                        rule_revision=rule.revision,
                        rule_snapshot=snapshot,
                    )
                )

    return matches


def _is_blocked_in_registry(targets: set[str]) -> bool:
    """Forward-compatible check for BlockedIdentifier once US-05A is merged."""
    for app_label in ("blocklist", "rules", "assessments"):
        try:
            model = apps.get_model(app_label, "BlockedIdentifier")
        except LookupError:
            continue
        return model.objects.filter(active=True, value__in=targets).exists()
    return False


def _evaluate_blocklist(ctx: EvaluationContext, rule: RiskRule) -> list[RuleMatch]:
    targets = {str(ctx.source_account_id)}
    if ctx.destination_target:
        targets.add(ctx.destination_target)

    params = rule.parameters or {}
    inline_blocked: set[str] = set()
    for key in ("blocked_ibans", "blocked_account_ids", "blocked_targets"):
        values = params.get(key)
        if isinstance(values, list):
            inline_blocked.update(str(item) for item in values)

    matched = bool(targets & inline_blocked) or _is_blocked_in_registry(targets)
    if not matched:
        return []

    decision = _resolve_rule_decision(params, default=DecisionType.REJECT)
    return [
        RuleMatch(
            code="BLOCKLIST_MATCH",
            message=f"Transaction matched blocklist rule '{rule.name}'.",
            decision=decision,
            rule_id=rule.id,
            rule_revision=rule.revision,
            rule_snapshot=build_rule_snapshot(rule),
        )
    ]


_EVALUATORS = {
    RiskRule.Type.AMOUNT_LIMIT: _evaluate_amount_limit,
    RiskRule.Type.BLOCKLIST: _evaluate_blocklist,
}


def evaluate_rules(ctx: EvaluationContext, rules: Iterable[RiskRule]) -> EvaluationResult:
    """Evaluate ledger signals and all active rules against `ctx`, aggregating by severity."""
    matches: list[RuleMatch] = []

    if ctx.ledger_history is not None and ctx.ledger_history.forced_decision:
        reason_code = ctx.ledger_history.reason_code or "LEDGER_UNAVAILABLE"
        reason_message = (
            "Source account was not found in S2-LDG ledger."
            if reason_code == STATUS_ACCOUNT_NOT_FOUND
            else "S2-LDG ledger service is unavailable or returned an invalid response."
        )
        matches.append(
            RuleMatch(
                code=reason_code,
                message=reason_message,
                decision=ctx.ledger_history.forced_decision,
            )
        )

    for rule in rules:
        evaluator = _EVALUATORS.get(rule.type)
        if evaluator is None:
            continue
        matches.extend(evaluator(ctx, rule))

    if not matches:
        default_reason = RuleMatch(
            code=DEFAULT_APPROVE_CODE,
            message=DEFAULT_APPROVE_MESSAGE,
            decision=DecisionType.APPROVE,
        )
        return EvaluationResult(decision=DecisionType.APPROVE, reasons=(default_reason,))

    final_decision = max(
        (m.decision for m in matches),
        key=lambda d: DECISION_SEVERITY[d],
    )
    return EvaluationResult(decision=final_decision, reasons=tuple(matches))
