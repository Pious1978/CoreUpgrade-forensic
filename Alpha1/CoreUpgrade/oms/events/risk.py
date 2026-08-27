from dataclasses import dataclass
from oms.events.base import BaseOrderEvent

@dataclass(frozen=True, slots=True)
class OrderAcceptedEvent(BaseOrderEvent):
    """Emitted when an intent passes risk and is formally accepted by the OMS.
    
    SEMANTICS: This represents internal OMS acceptance (OMS_ACCEPTED), *not* 
    broker acceptance. It guarantees the event stream is never empty for 
    processed intents, anchoring the execution timeline.
    """
    pass
