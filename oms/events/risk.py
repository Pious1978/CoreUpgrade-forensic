from dataclasses import dataclass
from oms.events.base import BaseOrderEvent

@dataclass(frozen=True, slots=True)
class OrderAcceptedEvent(BaseOrderEvent):
    pass

@dataclass(frozen=True, slots=True)
class RiskRejectedEvent(BaseOrderEvent):
    reason: str
