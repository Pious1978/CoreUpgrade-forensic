from dataclasses import dataclass, field
from decimal import Decimal
from portfolio.contracts.portfolio_contract import PortfolioContract

@dataclass(frozen=True, slots=True)
class PortfolioConstraintValidator:
    """
    Second-stage governance gate verifying that target portfolio weights, 
    cash buffers, and asset universes comply with institutional limits.
    """
    max_single_position_weight: Decimal = Decimal("0.25")  # 25% max per symbol
    min_cash_weight: Decimal = Decimal("0.05")             # 5% minimum cash reserve
    forbidden_symbols: tuple[str, ...] = field(default_factory=tuple)

    def validate(self, portfolio: PortfolioContract) -> tuple[str, ...]:
        """
        Inspects portfolio allocations and returns a tuple of violation descriptions.
        Empty tuple implies successful validation.
        """
        violations = []

        if portfolio.cash_weight < self.min_cash_weight:
            violations.append(
                f"Cash weight ({portfolio.cash_weight}) violates minimum reserve threshold "
                f"({self.min_cash_weight})."
            )

        for target in portfolio.targets:
            if target.symbol in self.forbidden_symbols:
                violations.append(f"Forbidden instrument detected in target allocation: '{target.symbol}'.")
            if target.target_weight > self.max_single_position_weight:
                violations.append(
                    f"Position '{target.symbol}' weight ({target.target_weight}) exceeds "
                    f"maximum single position limit ({self.max_single_position_weight})."
                )

        return tuple(violations)
