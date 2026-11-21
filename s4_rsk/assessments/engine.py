from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from django.apps import apps

from assessments.models import DecisionType, TransferType
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
    """Immutable transaction inputs passed into the rule engine."""

    transaction_id: UUID
    transfer_type: str
    source_account_id: UUID
    destination_account_id: UUID | None
    destination_iban: str | None
    amount: int
    currency: str

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


def _evaluate_amount_limit(ctx: EvaluationContext, rule: RiskRule) -> RuleMatch | None:
    max_amount = rule.parameters.get("max_amount")
    if isinstance(max_amount, bool) or not isinstance(max_amount, int):
        return None
    if ctx.amount <= max_amount:
        return None

    decision = _resolve_rule_decision(rule.parameters, default=DecisionType.REJECT)
    return RuleMatch(
        code="AMOUNT_LIMIT_EXCEEDED",
        message=f"Transaction amount {ctx.amount} IRR exceeds limit of {max_amount} IRR ({rule.name}).",
        decision=decision,
        rule_id=rule.id,
        rule_revision=rule.revision,
        rule_snapshot=build_rule_snapshot(rule),
    )


def _is_blocked_in_registry(targets: set[str]) -> bool:
    """Forward-compatible check for BlockedIdentifier once US-05A is merged."""
    for app_label in ("blocklist", "rules", "assessments"):
        try:
            model = apps.get_model(app_label, "BlockedIdentifier")
        except LookupError:
            continue
        return model.objects.filter(active=True, value__in=targets).exists()
    return False


def _evaluate_blocklist(ctx: EvaluationContext, rule: RiskRule) -> RuleMatch | None:
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
        return None

    decision = _resolve_rule_decision(params, default=DecisionType.REJECT)
    return RuleMatch(
        code="BLOCKLIST_MATCH",
        message=f"Transaction matched blocklist rule '{rule.name}'.",
        decision=decision,
        rule_id=rule.id,
        rule_revision=rule.revision,
        rule_snapshot=build_rule_snapshot(rule),
    )


_EVALUATORS = {
    RiskRule.Type.AMOUNT_LIMIT: _evaluate_amount_limit,
    RiskRule.Type.BLOCKLIST: _evaluate_blocklist,
}


def evaluate_rules(ctx: EvaluationContext, rules: Iterable[RiskRule]) -> EvaluationResult:
    """Evaluate all active rules against `ctx` and aggregate decision by severity."""
    matches: list[RuleMatch] = []

    for rule in rules:
        evaluator = _EVALUATORS.get(rule.type)
        if evaluator is None:
            continue
        match = evaluator(ctx, rule)
        if match is not None:
            matches.append(match)

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
