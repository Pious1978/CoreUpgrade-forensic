# execution/ems/paper_adapter.py
import uuid
from datetime import datetime
from execution.ems.base_adapter import AbstractEMSAdapter
from execution.contracts.ems_contract import EMSOrderRequest
from execution.contracts.broker_submission_contract import BrokerSubmissionResult

class PaperExchangeAdapter(AbstractEMSAdapter):
    """
    Deterministic simulated exchange adapter.

    Used for:
    - OMS replay testing
    - execution pipeline validation
    - failure simulation

    Contains zero portfolio logic.
    """

    @property
    def broker_name(self) -> str:
        return "PAPER_EXCHANGE"

    def submit(
        self,
        request: EMSOrderRequest
    ) -> BrokerSubmissionResult:

        return BrokerSubmissionResult(
            submission_id=str(uuid.uuid4()),
            ems_request_hash=request.request_hash,
            broker_name=self.broker_name,
            broker_order_id=f"PAPER-{uuid.uuid4()}",
            status="SUBMITTED",
            reject_reason=None,
            timestamp=datetime.utcnow()
        )

    def cancel(
        self,
        broker_order_id: str,
        portfolio_id: str,
        ems_request_hash: str
    ) -> BrokerSubmissionResult:

        return BrokerSubmissionResult(
            submission_id=str(uuid.uuid4()),
            ems_request_hash=ems_request_hash,
            broker_name=self.broker_name,
            broker_order_id=broker_order_id,
            status="CANCEL_REQUESTED",
            reject_reason=None,
            timestamp=datetime.utcnow()
        )
