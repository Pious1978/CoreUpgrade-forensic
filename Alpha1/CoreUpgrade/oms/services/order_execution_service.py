from typing import List
import uuid

from common.clock import Clock
from event_store.models.order_snapshot import OrderSnapshot
from event_store.projections.order_rehydrator import OrderRehydrator
from event_store.store_protocol import EventStore, StreamConcurrencyError
from oms.contracts.broker_order_status import BrokerOrderStatus
from oms.contracts.order_intent import OrderIntentContract
from oms.engine.execution_engine import ExecutionEngine
from oms.engine.order_management_engine import OrderManagementEngine
from oms.events.base import BaseOrderEvent
from oms.events.risk import OrderAcceptedEvent, RiskRejectedEvent
from oms.models.order import Order
from risk.contracts.risk_check_request import RiskCheckRequest
from risk.contracts.risk_check_result import RiskStatus


class DuplicateIntentError(Exception):
    """Raised when an intent ID has already been submitted to the execution service."""
    pass


class OrderExecutionService:
    """Outer boundary application service orchestrating the full CQRS lifecycle.
    
    Coordinates the flow of Intents -> Risk -> OMS -> Execution -> EventStore -> Snapshot.
    Treats the Event Store as the absolute source of truth for all command processing.
    """

    def __init__(
        self,
        oms_engine: OrderManagementEngine,
        execution_engine: ExecutionEngine,
        event_store: EventStore,
        clock: Clock
    ) -> None:
        self._oms = oms_engine
        self._exec_engine = execution_engine
        self._store = event_store
        self._clock = clock

    def _get_snapshot(self, intent: OrderIntentContract) -> OrderSnapshot:
        stream = self._store.read_stream(intent.intent_id)
        return OrderRehydrator.rebuild(intent=intent, events=stream)

    def submit_intent(
        self, 
        intent: OrderIntentContract, 
        risk_request: RiskCheckRequest
    ) -> OrderSnapshot:
        """Handles a new order intent, processes execution, and returns the resulting state."""
        if not isinstance(intent, OrderIntentContract):
            raise TypeError("intent must be an OrderIntentContract")
        if not isinstance(risk_request, RiskCheckRequest):
            raise TypeError("risk_request must be a RiskCheckRequest")

        events: List[BaseOrderEvent] = []
        now = self._clock.now()
        
        # 1. Risk Check & OMS Intake
        order, risk_result = self._oms.ingest_intent(intent, risk_request)
        
        if risk_result.status == RiskStatus.REJECTED:
            rejection_reasons = " | ".join([v.message for v in risk_result.violations])
            events.append(
                RiskRejectedEvent(
                    event_id=str(uuid.uuid4()),
                    intent_id=intent.intent_id,
                    execution_trace_id=intent.execution_trace_id,
                    timestamp=now,
                    reason=f"Policy Violations: {rejection_reasons}"
                )
            )
        else:
            events.append(
                OrderAcceptedEvent(
                    event_id=str(uuid.uuid4()),
                    intent_id=intent.intent_id,
                    execution_trace_id=intent.execution_trace_id,
                    timestamp=now
                )
            )
            # 2. Broker Execution
            if order:
                events.extend(self._exec_engine.execute_order(order))

        # 3. Persist Immutable Facts
        try:
            self._store.append_to_stream(
                stream_id=intent.intent_id, 
                events=tuple(events), 
                expected_version=0
            )
        except StreamConcurrencyError:
            raise DuplicateIntentError(f"Intent {intent.intent_id} has already been processed.")

        # 4. CQRS Read-Model Derivation
        return self._get_snapshot(intent)

    def process_broker_callback(
        self, 
        intent: OrderIntentContract, 
        status: BrokerOrderStatus
    ) -> OrderSnapshot:
        """Handles asynchronous webhook updates by rehydrating the write-model."""
        if not isinstance(intent, OrderIntentContract):
            raise TypeError("intent must be an OrderIntentContract")
        if not isinstance(status, BrokerOrderStatus):
            raise TypeError("status must be a BrokerOrderStatus")

        stream = self._store.read_stream(intent.intent_id)
        if not stream:
            raise ValueError(f"Cannot process callback: Stream {intent.intent_id} not found.")
            
        current_version = len(stream)
        order = Order.rehydrate(intent=intent, events=stream)

        new_events = self._exec_engine.process_broker_update(order, status)
        
        if new_events:
            self._store.append_to_stream(
                stream_id=intent.intent_id,
                events=new_events,
                expected_version=current_version
            )

        return self._get_snapshot(intent)
