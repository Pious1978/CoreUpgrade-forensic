from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass(frozen=True, slots=True)
class BrokerCapabilities:
    supports_short: bool = True
    supports_margin: bool = True
    supports_fractional: bool = False
    supports_stop_orders: bool = True
    supports_brackets: bool = False
    supports_after_hours: bool = False

@dataclass(frozen=True, slots=True)
class BrokerConfiguration:
    broker_name: str
    exchange: str = "NSE"
    timezone: str = "Asia/Kolkata"
    execution_mode: str = "PAPER"
    capabilities: BrokerCapabilities = field(default_factory=BrokerCapabilities)
    fee_model: Dict[str, Any] = field(default_factory=dict)
    margin_model: Dict[str, Any] = field(default_factory=dict)
