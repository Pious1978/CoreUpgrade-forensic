import time
from decimal import Decimal
from contracts.broker.order_contract import OrderContract
from contracts.broker.broker_response_contract import BrokerResponseContract
from contracts.broker.enums import OrderStatus
from .broker_interface import BrokerInterface
from .validators import ExecutionValidator
from .response_validator import BrokerResponseValidator
from .idempotency import IdempotencyGuard
from .order_state import OrderStateTracker
from .event_dispatcher import ExecutionEventDispatcher
from .events.order_events import OrderSubmissionRequestedEvent, OrderCancelledEvent
from .events.broker_events import BrokerAcceptedEvent, OrderRejectedEvent
from .events.execution_events import FillReceivedEvent

class ExecutionGateway:
    """
    Enterprise-grade execution boundary orchestrating strict state machines, 
    idempotency retry recovery, pre-call request event logging, response mapping, 
    and fill/rejection event dispatching.
    """
    STATUS_MAP = {
        OrderStatus.ACCEPTED: "ACCEPTED",
        OrderStatus.PARTIAL: "PARTIAL",
        OrderStatus.FILLED: "FILLED",
        OrderStatus.REJECTED: "REJECTED",
        OrderStatus.CANCELLED: "CANCELLED"
    }

    def __init__(self, broker_adapter: BrokerInterface, event_store=None):
        self.broker = broker_adapter
        self.event_dispatcher = ExecutionEventDispatcher(event_store=event_store)
        self.idempotency_guard = IdempotencyGuard()
        self.state_tracker = OrderStateTracker()

    def submit_order(self, order: OrderContract) -> BrokerResponseContract:
        # 1. Structural Validation
        ExecutionValidator.validate(order)

        # 2. State Machine Initialization & Validation Tracking
        self.state_tracker.create_order(order.order_id)
        self.state_tracker.update_state(order.order_id, "VALIDATED")

        # 3. Idempotency Check
        self.idempotency_guard.check(order.order_id, allow_retry=True)
        self.state_tracker.update_state(order.order_id, "SUBMITTED")

        timestamp = int(time.time() * 1000)

        # 4. Emit Request Event BEFORE Broker Transmission
        request_event = OrderSubmissionRequestedEvent(
            order_id=order.order_id,
            broker=order.broker_name,
            timestamp=timestamp,
            correlation_id=order.correlation_id
        )
        self.event_dispatcher.dispatch(request_event)

        try:
            # 5. Transmit to Broker Adapter
            response = self.broker.submit_order(order)
            BrokerResponseValidator.validate(order, response)
        except (ConnectionError, TimeoutError, ValueError) as ex:
            # Narrowly catch operational network/broker errors (avoid masking programming bugs)
            self.idempotency_guard.record_failure(order.order_id)
            self.state_tracker.update_state(order.order_id, "REJECTED")
            
            reject_event = OrderRejectedEvent(
                order_id=order.order_id,
                error_message=str(ex),
                broker=order.broker_name,
                timestamp=int(time.time() * 1000),
                correlation_id=order.correlation_id
            )
            self.event_dispatcher.dispatch(reject_event)
            raise ex

        # 6. Handle Broker Response Status & Idempotency Failure Tracking for Rejections
        mapped_state = self.STATUS_MAP.get(response.status, "UNKNOWN")
        self.state_tracker.update_state(order.order_id, mapped_state)

        if response.status == OrderStatus.REJECTED:
            self.idempotency_guard.record_failure(order.order_id)
            reject_event = OrderRejectedEvent(
                order_id=order.order_id,
                error_message=response.error_message or "Broker rejected order",
                broker=order.broker_name,
                timestamp=int(time.time() * 1000),
                correlation_id=order.correlation_id
            )
            self.event_dispatcher.dispatch(reject_event)
            return response

        # 7. Emit Acceptance / Fill Events
        if response.status in {OrderStatus.ACCEPTED, OrderStatus.PARTIAL, OrderStatus.FILLED}:
            accepted_event = BrokerAcceptedEvent(
                order_id=order.order_id,
                broker_order_id=response.broker_order_id or "UNKNOWN",
                broker=order.broker_name,
                timestamp=int(time.time() * 1000),
                correlation_id=order.correlation_id
            )
            self.event_dispatcher.dispatch(accepted_event)

        if response.filled_quantity > 0:
            fill_event = FillReceivedEvent(
                execution_id=f"EXEC-{order.order_id}-{int(time.time())}",
                order_id=order.order_id,
                filled_quantity=response.filled_quantity,
                fill_price=response.average_fill_price or order.limit_price or Decimal("0"),
                broker=order.broker_name,
                timestamp=int(time.time() * 1000),
                correlation_id=order.correlation_id
            )
            self.event_dispatcher.dispatch(fill_event)

        return response

    def cancel_order(self, order_id: str, correlation_id: str) -> BrokerResponseContract:
        if not order_id or not correlation_id:
            raise ValueError("Cancellation requires valid order_id and correlation_id for traceability")

        response = self.broker.cancel_order(order_id)
        self.state_tracker.update_state(order_id, "CANCELLED")

        cancel_event = OrderCancelledEvent(
            order_id=order_id,
            broker=response.broker_name,
            timestamp=int(time.time() * 1000),
            correlation_id=correlation_id
        )
        self.event_dispatcher.dispatch(cancel_event)

        return response

    def get_order_status(self, order_id: str) -> BrokerResponseContract:
        return self.broker.get_order_status(order_id)
