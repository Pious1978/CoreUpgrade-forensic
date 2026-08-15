from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Tuple

from portfolio.contracts.certified_strategy_contract import CertifiedStrategyContract
from portfolio.contracts.position_target_contract import PositionTargetContract
from portfolio.contracts.portfolio_contract import PortfolioContract

@dataclass(frozen=True, slots=True)
class PortfolioBuilder:
    """
    Core portfolio construction engine transforming a certified strategy 
    and capital constraints into an immutable, versioned portfolio allocation intent.
    """
    model_version: str = "MeanVarianceOptimizer-v2.1"

    def build(
        self,
        portfolio_id: str,
        certified_strategy: CertifiedStrategyContract,
        capital: Decimal,
        currency: str,
        target_weights: dict[str, tuple[Decimal, str, str]],  # symbol -> (weight, asset_class, reason)
        asset_prices: dict[str, Decimal],                     # symbol -> market price
        timestamp: datetime,
    ) -> PortfolioContract:
        """
        Constructs and validates a target portfolio snapshot.
        """
        if capital <= Decimal("0"):
            raise ValueError("Capital allocation must be greater than zero.")
        if capital > certified_strategy.max_capital_allocation:
            raise ValueError(
                f"Requested capital ({capital}) exceeds certified maximum allocation "
                f"({certified_strategy.max_capital_allocation}) for strategy '{certified_strategy.strategy_id}'."
            )

        targets = []
        total_target_weight = Decimal("0")

        for symbol, (weight, asset_class, reason) in target_weights.items():
            if symbol not in asset_prices:
                raise ValueError(f"Missing market price for symbol '{symbol}' required for quantity calculation.")
            
            price = asset_prices[symbol]
            if price <= Decimal("0"):
                raise ValueError(f"Market price for '{symbol}' must be positive.")

            # Calculate target quantity based on capital weight and asset price
            allocated_capital = capital * weight
            target_qty = (allocated_capital / price).quantize(Decimal("0.0001"))

            target = PositionTargetContract(
                symbol=symbol,
                target_weight=weight,
                target_quantity=target_qty,
                asset_class=asset_class,
                currency=currency,
                reason=reason,
            )
            targets.append(target)
            total_target_weight += weight

        # Residual cash weight calculation
        cash_weight = Decimal("1") - total_target_weight
        if cash_weight < Decimal("0"):
            raise ValueError("Total target weights exceed 100% of available capital.")

        return PortfolioContract(
            portfolio_id=portfolio_id,
            strategy_id=certified_strategy.strategy_id,
            construction_model_version=self.model_version,
            currency=currency,
            targets=tuple(targets),
            cash_weight=cash_weight,
            timestamp=timestamp,
        )
