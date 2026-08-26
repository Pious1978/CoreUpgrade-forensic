from dataclasses import dataclass
from decimal import Decimal
import hashlib

from portfolio.contracts.portfolio_contract import PortfolioContract
from portfolio.contracts.holdings_snapshot_contract import HoldingsSnapshotContract
from portfolio.contracts.rebalance_instruction_contract import (
    RebalanceInstructionContract,
    RebalanceAction,
)
from portfolio.engines.portfolio_constraint_validator import (
    PortfolioConstraintValidator,
)
from portfolio.policies.rebalance_policy import RebalancePolicy


@dataclass(frozen=True, slots=True)
class RebalanceEngine:
    """
    Engine responsible for comparing account holdings against target portfolio
    allocations, enforcing portfolio constraints, applying rebalance policy
    tolerances, and generating deterministic rebalance instructions.

    The engine must never generate executable rebalance instructions from an
    invalid PortfolioContract.
    """

    policy: RebalancePolicy = RebalancePolicy()
    constraint_validator: PortfolioConstraintValidator = (
        PortfolioConstraintValidator()
    )

    def generate_instructions(
        self,
        portfolio_contract: PortfolioContract,
        holdings_snapshot: HoldingsSnapshotContract,
    ) -> tuple[RebalanceInstructionContract, ...]:
        """
        Validate the portfolio before generating any rebalance instructions.

        Flow:

            PortfolioContract
                |
                v
            PortfolioConstraintValidator
                |
          PASS / FAIL
                |
                v
            RebalanceEngine
                |
                v
            RebalanceInstructionContract

        An invalid portfolio is a hard stop. No rebalance instruction is
        generated from an invalid portfolio.
        """

        violations = self.constraint_validator.validate(
            portfolio_contract
        )

        if violations:
            raise ValueError(
                "Portfolio constraint validation failed; "
                "rebalance instructions cannot be generated: "
                + " | ".join(violations)
            )

        instructions: list[RebalanceInstructionContract] = []

        target_map = {
            target.symbol: target.target_quantity
            for target in portfolio_contract.targets
        }

        current_map = {
            holding.symbol: holding.quantity
            for holding in holdings_snapshot.holdings
        }

        all_symbols = sorted(
            set(target_map.keys()).union(current_map.keys())
        )

        for symbol in all_symbols:
            current_qty = current_map.get(
                symbol,
                Decimal("0"),
            )

            target_qty = target_map.get(
                symbol,
                Decimal("0"),
            )

            signed_delta = target_qty - current_qty

            # Skip changes within the configured rebalance tolerance.
            if abs(signed_delta) < self.policy.minimum_quantity_change:
                continue

            action = (
                RebalanceAction.BUY
                if signed_delta > Decimal("0")
                else RebalanceAction.SELL
            )

            # Deterministic instruction ID derived from the complete
            # rebalance state relevant to this instruction.
            hasher = hashlib.sha256()

            hasher.update(
                portfolio_contract.portfolio_id.encode("utf-8")
            )
            hasher.update(
                symbol.encode("utf-8")
            )
            hasher.update(
                str(current_qty).encode("utf-8")
            )
            hasher.update(
                str(target_qty).encode("utf-8")
            )
            hasher.update(
                holdings_snapshot.snapshot_id.encode("utf-8")
            )

            instruction_id = (
                f"REB-{hasher.hexdigest()[:16].upper()}"
            )

            instruction = RebalanceInstructionContract(
                instruction_id=instruction_id,
                portfolio_id=portfolio_contract.portfolio_id,
                symbol=symbol,
                action=action,
                current_quantity=current_qty,
                target_quantity=target_qty,
                signed_delta_quantity=signed_delta,
                reason=self.policy.rebalance_reason,
            )

            instructions.append(instruction)

        return tuple(instructions)