from abc import ABC, abstractmethod

from execution.contracts.event_gateway_contract import GatewayIngressPayload
from execution.events.normalization_result import EventNormalizationResult


class AbstractEventNormalizer(ABC):
    """
    Converts broker-specific payload formats
    into canonical ExecutionEvent objects.

    Has no OMS authority.
    Has no portfolio authority.
    """

    @property
    @abstractmethod
    def broker_name(self) -> str:
        pass


    @property
    @abstractmethod
    def version(self) -> str:
        pass


    @abstractmethod
    def normalize(
        self,
        ingress: GatewayIngressPayload
    ) -> EventNormalizationResult:
        pass
