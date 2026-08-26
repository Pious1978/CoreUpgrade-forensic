
# execution/translation/portfolio_to_execution.py

from datetime import datetime

from portfolio.contracts.portfolio_certificate import PortfolioCertificate
from portfolio.contracts.rebalance_instruction_contract import (
    RebalanceInstructionContract,
)

from execution.contracts.execution_intent import ExecutionIntent


def translate_rebalance_to_intent(
    instruction: RebalanceInstructionContract,
    certificate: PortfolioCertificate,
    *,
    execution_policy_id: str,
    urgency: str,
    timestamp: datetime,
) -> ExecutionIntent:
    """
    Canonical Portfolio → Execution translation boundary.

    Converts an immutable, validated RebalanceInstructionContract
    into the repository's single canonical ExecutionIntent.

    No execution decision is made here.
    No OMS order is constructed here.
    """

    if not certificate.certified:
        raise ValueError(
            "Cannot translate rebalance instruction from uncertified "
            "PortfolioCertificate."
        )

    if instruction.portfolio_id != certificate.portfolio_id:
        raise ValueError(
            "Portfolio ID mismatch between RebalanceInstructionContract "
            "and PortfolioCertificate."
        )

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(
            "Execution translation requires a timezone-aware timestamp."
        )

    return ExecutionIntent(
        intent_id=instruction.instruction_id,
        portfolio_certificate_hash=certificate.certificate_hash,
        portfolio_id=instruction.portfolio_id,
        instrument_id=instruction.symbol,
        current_position=instruction.current_quantity,
        target_position=instruction.target_quantity,
        delta_quantity=instruction.signed_delta_quantity,
        urgency=urgency,
        execution_policy_id=execution_policy_id,
        timestamp=timestamp,
    )

