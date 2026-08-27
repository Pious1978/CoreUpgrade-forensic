import time
from contracts.broker.order_contract import OrderContract
from contracts.broker.broker_response_contract import BrokerResponseContract
from contracts.broker.enums import OrderStatus
from .broker_interface import BrokerInterface
from .validators import ExecutionValidator
from .response_validator import BrokerResponseValidator
from .idempotency import IdempotencyGuard
from .order_state import OrderStateTracker
from .events.order_events import OrderSubmittedEvent, OrderCancelledEvent
from .events.broker_events import BrokerAcceptedEvent, OrderRejectedEvent

class ExecutionGateway:
    """
    Hardened execution boundary orchestrating validation, idempotency recovery,
    lifecycle state tracking, response verification, and event store persistence.
    """
    def __init__(self, broker_adapter: BrokerInterface, event_store=None):
        self.broker = broker_adapter
        self.event_store = event_store
        self.idempotency_guard = IdempotencyGuard()
        self.state_tracker = OrderStateTracker()

    def submit_order(self, order: OrderContract) -> BrokerResponseContract:
        ExecutionValidator.validate(order)
        self.state_tracker.update_state(order.order_id, "VALIDATED")

        self.idempotency_guard.check(order.order_id, allow_retry=True)
        self.state_tracker.update_state(order.order_id, "SUBMITTED")

        timestamp = int(time.time() * 1000)

        try:
            response = self.broker.submit_order(order)
            BrokerResponseValidator.validate(order, response)
        except Exception as ex:
            self.idempotency_guard.record_failure(order.order_id)
            self.state_tracker.update_state(order.order_id, "REJECTED")
            
            if self.event_store:
                reject_event = OrderRejectedEvent(
                    order_id=order.order_id,
                    error_message=str(ex),
                    broker=order.broker_name,
                    timestamp=timestamp,
                    correlation_id=order.correlation_id
                )
                self.event_store.append(reject_event)
            raise ex

        if self.event_store:
            submission_event = OrderSubmittedEvent(
                order_id=order.order_id,
                broker=order.broker_name,
                timestamp=timestamp,
                correlation_id=order.correlation_id
            )
            self.event_store.append(submission_event)

            if response.status in {OrderStatus.ACCEPTED, OrderStatus.FILLED}:
                accepted_event = BrokerAcceptedEvent(
                    order_id=order.order_id,
                    broker_order_id=response.broker_order_id or "UNKNOWN",
                    broker=order.broker_name,
                    timestamp=timestamp,
                    correlation_id=order.correlation_id
                )
                self.event_store.append(accepted_event)
                self.state_tracker.update_state(order.order_id, response.status.value)

        return response

    def cancel_order(self, order_id: str, correlation_id: str) -> BrokerResponseContract:
        if not order_id or not correlation_id:
            raise ValueError("Cancellation requires valid order_id and correlation_id for traceability")

        response = self.broker.cancel_order(order_id)
        self.state_tracker.update_state(order_id, "CANCELLED")

        if self.event_store:
            cancel_event = OrderCancelledEvent(
                order_id=order_id,
                broker=response.broker_name,
                timestamp=int(time.time() * 1000),
                correlation_id=correlation_id
            )
            self.event_store.append(cancel_event)

        return response

    def get_order_status(self, order_id: str) -> BrokerResponseContract:
        return self.broker.get_order_status(order_id)
