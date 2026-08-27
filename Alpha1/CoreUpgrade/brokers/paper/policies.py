from dataclasses import dataclass
from typing import Protocol, List, Tuple, Optional
from .configuration import BrokerCapabilities

class OrderPolicy(Protocol):
    def validate(self, order, capabilities: BrokerCapabilities) -> Tuple[bool, Optional[str]]:
        ...

class MarketHoursPolicy:
    def validate(self, order, capabilities: BrokerCapabilities) -> Tuple[bool, Optional[str]]:
        # Can check exchange timing state or flags
        return True, None

class BrokerCapabilityPolicy:
    def validate(self, order, capabilities: BrokerCapabilities) -> Tuple[bool, Optional[str]]:
        if order.side == OrderSide.SELL and not capabilities.supports_short:
            return False, "Broker does not support short selling."
        if getattr(order, 'is_fractional', False) and not capabilities.supports_fractional:
            return False, "Broker does not support fractional shares."
        if getattr(order, 'order_type', OrderType.MARKET) == OrderType.STOP and not capabilities.supports_stop_orders:
            return False, "Broker does not support stop orders."
        return True, None

class RiskPolicy:
    def validate(self, order, capabilities: BrokerCapabilities) -> Tuple[bool, Optional[str]]:
        if order.quantity <= 0:
            return False, "Order quantity must be greater than zero."
        return True, None

class PolicyChain:
    def __init__(self, policies: List[OrderPolicy] = None):
        self.policies = policies or [MarketHoursPolicy(), BrokerCapabilityPolicy(), RiskPolicy()]

    def validate(self, order, capabilities: BrokerCapabilities) -> Tuple[bool, Optional[str]]:
        for policy in self.policies:
            valid, err = policy.validate(order, capabilities)
            if not valid:
                return False, err
        return True, None
