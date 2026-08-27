from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Immutable configuration container defining operational risk limits.

    Enforces declarative, versioned, and governance-controlled risk parameters
    with strict type safety and relational business validation.
    """
    policy_version: str
    max_position_weight: Decimal        # e.g., Decimal("0.20") for 20%
    max_sector_exposure: Decimal        # e.g., Decimal("0.40") for 40%
    max_order_value: Decimal            # Absolute currency limit per order
    max_daily_loss: Decimal             # Positive magnitude fraction, e.g., Decimal("0.05") for 5%
    max_portfolio_drawdown: Decimal     # Positive magnitude fraction, e.g., Decimal("0.15") for 15%
    max_liquidity_participation: Decimal # e.g., Decimal("0.10") for 10% of ADV
    kill_switch_enabled: bool

    def __post_init__(self) -> None:
        """Enforces type safety, structural bounds, and relational consistency."""
        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise ValueError("policy_version must be a non-empty string")

        # Strict Decimal Type Verification
        numeric_fields = {
            "max_position_weight": self.max_position_weight,
            "max_sector_exposure": self.max_sector_exposure,
            "max_order_value": self.max_order_value,
            "max_daily_loss": self.max_daily_loss,
            "max_portfolio_drawdown": self.max_portfolio_drawdown,
            "max_liquidity_participation": self.max_liquidity_participation,
        }
        for name, val in numeric_fields.items():
            if not isinstance(val, Decimal):
                raise TypeError(f"{name} must be an instance of Decimal, got {type(val)}")

        if not (Decimal("0") < self.max_position_weight <= Decimal("1")):
            raise ValueError("max_position_weight must be between 0 and 1")

        if not (Decimal("0") < self.max_sector_exposure <= Decimal("1")):
            raise ValueError("max_sector_exposure must be between 0 and 1")

        # Relational Consistency Check
        if self.max_position_weight > self.max_sector_exposure:
            raise ValueError("max_position_weight cannot exceed max_sector_exposure")

        if self.max_order_value <= Decimal("0"):
            raise ValueError("max_order_value must be positive")

        if not (Decimal("0") < self.max_daily_loss < Decimal("1")):
            raise ValueError("max_daily_loss must be a positive fraction between 0 and 1 (e.g., 0.05 for 5%)")

        if not (Decimal("0") < self.max_portfolio_drawdown < Decimal("1")):
            raise ValueError("max_portfolio_drawdown must be a positive fraction between 0 and 1 (e.g., 0.15 for 15%)")

        if not (Decimal("0") < self.max_liquidity_participation <= Decimal("1")):
            raise ValueError("max_liquidity_participation must be between 0 and 1")
