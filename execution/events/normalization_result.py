# execution/events/normalization_result.py

import dataclasses
from execution.contracts.execution_event import ExecutionEvent
from research.governance.serialization import CanonicalSerializer


@dataclasses.dataclass(frozen=True)
class EventNormalizationResult:
    """
    Immutable result of converting a raw broker payload
    into an internal ExecutionEvent.

    Contains both:
    - normalized event
    - originating ingress lineage
    """

    ingress_hash: str
    execution_event: ExecutionEvent
    normalizer_name: str
    normalizer_version: str

    @property
    def normalization_hash(self) -> str:
        return CanonicalSerializer.hash(self)
