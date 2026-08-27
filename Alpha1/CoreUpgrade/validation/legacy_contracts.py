from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import math
import pytz
import uuid

IST = pytz.timezone("Asia/Kolkata")
TRADE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "institutional_alpha_engine")

@dataclass
class TradeRecord:
    symbol: str
    entry_date: datetime
    exit_date: datetime
    r_multiple: float
    net_return: float
    strategy_name: str = "DEFAULT"
    signal_type: str = "DEFAULT"
    risk_pct: float = 0.01
    capital_weight: float = 1.0
    sector: str = "UNKNOWN"
    market_regime: str = "BULL"
    trade_id: Optional[str] = None

    def __post_init__(self):
        # 1. Timezone normalization to IST (Asia/Kolkata)
        if self.entry_date.tzinfo is None:
            self.entry_date = IST.localize(self.entry_date)
        else:
            self.entry_date = self.entry_date.astimezone(IST)

        if self.exit_date.tzinfo is None:
            self.exit_date = IST.localize(self.exit_date)
        else:
            self.exit_date = self.exit_date.astimezone(IST)

        # 2. String normalization
        if isinstance(self.market_regime, str):
            self.market_regime = self.market_regime.upper()
        
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("TradeRecord must have a valid string symbol.")
        self.symbol = self.symbol.upper()

        # 3. Strict numerical type and NaN/Inf validation
        for field_name, val in [
            ("r_multiple", self.r_multiple),
            ("net_return", self.net_return),
            ("risk_pct", self.risk_pct),
            ("capital_weight", self.capital_weight)
        ]:
            if not isinstance(val, (int, float)):
                raise TypeError(f"{field_name} must be numeric, got {type(val)}.")
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"{field_name} contains invalid numeric value: {val}")

        # 4. Financial and capital bounds checks (Contracts prevent bad objects)
        if self.risk_pct <= 0 or self.risk_pct > 0.05:
            raise ValueError(f"Trade risk_pct ({self.risk_pct}) must be strictly between 0 and 5% (0.05).")
        if self.capital_weight < 0 or self.capital_weight > 1.0:
            raise ValueError(f"Trade capital_weight ({self.capital_weight}) must be between 0 and 1.0 (100%).")
        if self.net_return <= -1.0:
            raise ValueError(f"Trade net_return ({self.net_return}) cannot exceed -100% loss.")
        if abs(self.r_multiple) > 20:
            raise ValueError(f"Abnormal R multiple detected ({self.r_multiple}). Max allowed absolute R is 20.")

        # 5. Timeline consistency
        if self.exit_date < self.entry_date:
            raise ValueError(f"Invalid trade timeline for {self.symbol}: exit_date ({self.exit_date}) cannot precede entry_date ({self.entry_date}).")

        # 6. Context-aware deterministic UUID5 generation using institutional namespace
        if not self.trade_id:
            raw = (
                f"{self.symbol}|"
                f"{self.entry_date.isoformat()}|"
                f"{self.exit_date.isoformat()}|"
                f"{self.strategy_name}|"
                f"{self.signal_type}|"
                f"{self.market_regime}|"
                f"{float(self.r_multiple)}"
            )
            self.trade_id = "TRD_" + str(uuid.uuid5(TRADE_NAMESPACE, raw))[:12]

    @property
    def holding_days(self) -> int:
        """Calculates holding duration for alpha decay and capital efficiency analysis."""
        return max(0, (self.exit_date - self.entry_date).days)
