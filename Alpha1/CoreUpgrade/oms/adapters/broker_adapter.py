from typing import Protocol

from oms.contracts.broker_order_status import BrokerOrderStatus
from oms.contracts.broker_submission_result import BrokerSubmissionResult
from oms.models.order import Order


class BrokerAdapter(Protocol):
    """Anti-corruption layer protocol defining the required contract for all 
    external broker integrations.
    """

    def submit_order(self, order: Order) -> BrokerSubmissionResult:
        """Translates the Order intent into a broker API submission.
        
        Raises:
            BrokerOrderRejectionError: If the broker rejects the order immediately.
            BrokerNetworkError: On connection failures.
            BrokerAuthenticationError: On auth failures.
            BrokerRateLimitError: If API limits are hit.
        """
        ...

    def cancel_order(self, order: Order) -> None:
        """Translates an internal cancellation request into a broker API cancellation.
        
        Requires the Order to have an assigned broker_order_id.
        """
        ...
        
    def get_order_status(self, broker_order_id: str) -> BrokerOrderStatus:
        """Fetches the current status of an order directly from the broker."""
        ...
