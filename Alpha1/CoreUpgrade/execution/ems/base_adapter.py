# execution/ems/base_adapter.py
from abc import ABC, abstractmethod
from execution.contracts.ems_contract import EMSOrderRequest
from execution.contracts.broker_submission_contract import BrokerSubmissionResult

class AbstractEMSAdapter(ABC):
    """
    Pure infrastructure boundary for broker execution routing.
    Isolated entirely from portfolio composition, risk models, and constraints.
    """

    @property
    @abstractmethod
    def broker_name(self) -> str:
        pass

    @abstractmethod
    def submit(
        self,
        request: EMSOrderRequest
    ) -> BrokerSubmissionResult:
        """Submits a standardized EMS order request to the external broker venue."""
        pass

    @abstractmethod
    def cancel(
        self,
        broker_order_id: str,
        portfolio_id: str,
        ems_request_hash: str
    ) -> BrokerSubmissionResult:
        """Requests cancellation of an active order while preserving cryptographic lineage."""
        pass
