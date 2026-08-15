from dataclasses import dataclass
from .broker_capabilities import BrokerCapabilities
from .account_capabilities import AccountCapabilities

@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    allowed: bool
    broker_support: bool
    account_permission: bool

    @property
    def reason(self) -> str | None:
        if self.allowed:
            return None
        if not self.broker_support:
            return "BROKER_UNSUPPORTED"
        if not self.account_permission:
            return "ACCOUNT_RESTRICTED"
        return "UNKNOWN"

@dataclass(frozen=True, slots=True)
class EffectiveCapabilities:
    shorting: CapabilityDecision
    margin: CapabilityDecision
    fractional: CapabilityDecision
    cancel: CapabilityDecision
    stop_orders: CapabilityDecision

    @classmethod
    def from_pair(cls, broker: BrokerCapabilities, account: AccountCapabilities) -> "EffectiveCapabilities":
        return cls(
            shorting=CapabilityDecision(
                allowed=broker.supports_shorting and account.allows_shorting,
                broker_support=broker.supports_shorting,
                account_permission=account.allows_shorting,
            ),
            margin=CapabilityDecision(
                allowed=broker.supports_margin and account.allows_margin,
                broker_support=broker.supports_margin,
                account_permission=account.allows_margin,
            ),
            fractional=CapabilityDecision(
                allowed=broker.supports_fractional and account.allows_fractional,
                broker_support=broker.supports_fractional,
                account_permission=account.allows_fractional,
            ),
            cancel=CapabilityDecision(
                allowed=broker.supports_cancel and account.allows_cancel,
                broker_support=broker.supports_cancel,
                account_permission=account.allows_cancel,
            ),
            stop_orders=CapabilityDecision(
                allowed=broker.supports_stop_orders and account.allows_stop_orders,
                broker_support=broker.supports_stop_orders,
                account_permission=account.allows_stop_orders,
            ),
        )
