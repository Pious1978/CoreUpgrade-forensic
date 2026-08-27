from dataclasses import dataclass
from decimal import Decimal
import hashlib
from typing import Dict, Tuple

from portfolio.contracts.portfolio_contract import PortfolioContract
from portfolio.contracts.holdings_snapshot_contract import HoldingsSnapshotContract
from portfolio.contracts.rebalance_instruction_contract import (
    RebalanceInstructionContract,
    RebalanceAction,
)
from portfolio.policies.rebalance_policy import RebalancePolicy

@dataclass(frozen=True, slots=True)
class RebalanceEngine:
    """
    Engine responsible for comparing account holdings against target portfolio allocations,
    applying rebalance policy tolerances, and generating deterministic, hashed instructions.
    """
    policy: RebalancePolicy = RebalancePolicy()

    def generate_instructions(
        self,
        portfolio_contract: PortfolioContract,
        holdings_snapshot: HoldingsSnapshotContract,
    ) -> tuple[RebalanceInstructionContract, ...]:
        """
        Computes signed deltas, filters out noise below policy thresholds, 
        liquidates legacy positions, and outputs cryptographically hashed instructions.
        """
        instructions = []
        
        target_map = {target.symbol: target.target_quantity for target in portfolio_contract.targets}
        current_map = {h.symbol: h.quantity for h in holdings_snapshot.holdings}
        all_symbols = sorted(set(target_map.keys()).union(set(current_map.keys())))

        for symbol in all_symbols:
            current_qty = current_map.get(symbol, Decimal("0"))
            target_qty = target_map.get(symbol, Decimal("0"))
            signed_delta = target_qty - current_qty

            # Skip instruction if change is within policy tolerance (filters out HOLD noise)
            if abs(signed_delta) < self.policy.minimum_quantity_change:
                continue

            action = RebalanceAction.BUY if signed_delta > Decimal("0") else RebalanceAction.SELL

            # Cryptographic deterministic instruction ID derivation
            hasher = hashlib.sha256()
            hasher.update(portfolio_contract.portfolio_id.encode("utf-8"))
            hasher.update(symbol.encode("utf-8"))
            hasher.update(str(current_qty).encode("utf-8"))
            hasher.update(str(target_qty).encode("utf-8"))
            hasher.update(holdings_snapshot.snapshot_id.encode("utf-8"))
            instruction_id = f"REB-{hasher.hexdigest()[:16].upper()}"

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
