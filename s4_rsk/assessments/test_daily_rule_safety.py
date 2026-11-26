from uuid import uuid4

from assessments.engine import EvaluationContext, evaluate_rules
from assessments.models import DecisionType, TransferType
from rules.models import RiskRule


def test_daily_limit_requires_ledger_history():
    context = EvaluationContext(
        transaction_id=uuid4(),
        transfer_type=TransferType.INTERNAL,
        source_account_id=uuid4(),
        destination_account_id=uuid4(),
        destination_iban=None,
        amount=10,
        currency="IRR",
    )
    rule = RiskRule(name="Daily limit", type=RiskRule.Type.AMOUNT_LIMIT,
                    parameters={"max_amount": 100, "max_daily_count": 2})

    result = evaluate_rules(context, [rule])

    assert result.decision == DecisionType.REVIEW
    assert result.reasons[0].code == "LEDGER_UNAVAILABLE"
    assert result.reasons[0].rule_id == rule.id
