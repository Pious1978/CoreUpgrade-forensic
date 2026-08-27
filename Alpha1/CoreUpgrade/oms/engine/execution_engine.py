from datetime import datetime, timezone
from typing import List, Tuple
import uuid

from oms.adapters.broker_adapter import BrokerAdapter
from oms.adapters.exceptions import BrokerIntegrationError, BrokerOrderRejectionError
from oms.contracts.broker_order_status import BrokerOrderStatus
from oms.contracts.broker_submission_result import BrokerSubmissionResult
from oms.events.order_events import (
    BaseOrderEvent,
    OrderExecutionErrorEvent,
    OrderRejectedEvent,
    OrderSubmittedEvent,
    OrderTransitionEvent,
)
from oms.models.order import Order
from oms.state_machine.order_state_machine import OrderState


class ExecutionEngine:
    """Drives risk-approved Orders through the broker boundary, manages asynchronous
    state transitions, and emits immutable events for the Event Store.
    """

    def __init__(self, broker_adapter: BrokerAdapter) -> None:
        self._adapter = broker_adapter

    def execute_order(self, order: Order) -> Tuple[BaseOrderEvent, ...]:
        """Attempts to submit a risk-approved order to the broker.
        
        Returns an immutable tuple of events resulting from the execution attempt.
        """
        if not isinstance(order, Order):
            raise TypeError(f"order must be an instance of Order, got {type(order)}")

        events: List[BaseOrderEvent] = []
        # Future enhancement: Inject a Clock dependency here for deterministic replay
        now = datetime.now(timezone.utc) 

        if order.state != OrderState.SUBMITTED:
            raise ValueError(f"Order {order.intent.intent_id} must be in SUBMITTED state to execute. Found: {order.state.value}")

        try:
            # 1. Delegate to Anti-Corruption Layer
            result: BrokerSubmissionResult = self._adapter.submit_order(order)
            
            # 2. Update Internal Aggregate
            order.set_broker_order_id(result.broker_order_id)

            # 3. Emit Submission Fact
            events.append(
                OrderSubmittedEvent(
                    event_id=str(uuid.uuid4()),
                    intent_id=order.intent.intent_id,
                    execution_trace_id=order.intent.execution_trace_id,
                    timestamp=result.accepted_at,
                    broker_order_id=result.broker_order_id,
                    exchange_order_id=result.exchange_order_id
                )
            )

        except BrokerOrderRejectionError as e:
            order.transition(OrderState.REJECTED)
            events.append(
                OrderRejectedEvent(
                    event_id=str(uuid.uuid4()),
                    intent_id=order.intent.intent_id,
                    execution_trace_id=order.intent.execution_trace_id,
                    timestamp=now,
                    reason=str(e),
                    source="BROKER"
                )
            )
            
        except BrokerIntegrationError as e:
            # Emit error fact for reconciliation without mutating Order state
            events.append(
                OrderExecutionErrorEvent(
                    event_id=str(uuid.uuid4()),
                    intent_id=order.intent.intent_id,
                    execution_trace_id=order.intent.execution_trace_id,
                    timestamp=now,
                    error_message=str(e),
                    error_type=type(e).__name__
                )
            )

        return tuple(events)

    def process_broker_update(self, order: Order, status: BrokerOrderStatus) -> Tuple[BaseOrderEvent, ...]:
        """Processes normalized status updates and applies downstream state transitions."""
        if not isinstance(order, Order):
            raise TypeError(f"order must be an instance of Order, got {type(order)}")
        if not isinstance(status, BrokerOrderStatus):
            raise TypeError(f"status must be an instance of BrokerOrderStatus, got {type(status)}")
            
        # Critical Reconciliation Invariant
        if order.broker_order_id != status.broker_order_id:
            raise ValueError(
                f"Broker status ID ({status.broker_order_id}) does not match "
                f"the Order's broker_order_id ({order.broker_order_id})"
            )

        events: List[BaseOrderEvent] = []
        now = datetime.now(timezone.utc)

        if order.state == status.state:
            return tuple(events)

        if order.can_transition(status.state):
            from_state = order.state
            order.transition(status.state)
            
            events.append(
                OrderTransitionEvent(
                    event_id=str(uuid.uuid4()),
                    intent_id=order.intent.intent_id,
                    execution_trace_id=order.intent.execution_trace_id,
                    timestamp=now,
                    from_state=from_state,
                    to_state=status.state,
                    filled_quantity=status.filled_quantity,
                    remaining_quantity=status.remaining_quantity,
                    average_fill_price=status.average_fill_price
                )
            )
        else:
            raise ValueError(
                f"Broker reported state '{status.state.value}', but OMS OrderStateMachine "
                f"rejects transition from '{order.state.value}'."
            )

        return tuple(events)
