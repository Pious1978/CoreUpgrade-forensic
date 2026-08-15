import dataclasses
from decimal import Decimal
from .contracts import ExecutionReportContract, ExecutionOutcome
from .events import (
    OrderSubmittedEvent,
    OrderAcceptedEvent,
    PartialFillEvent,
    FillReceivedEvent,
    PositionUpdatedEvent,
    AccountUpdatedEvent,
    OrderCancelledEvent,
    OrderRejectedEvent,
    OrderCompletedEvent
)

class ExecutionCommitEngine:
    def __init__(self, account_engine, position_engine, repository, event_store, event_dispatcher=None):
        self.account_engine = account_engine
        self.position_engine = position_engine
        self.repository = repository
        self.event_store = event_store
        self.event_dispatcher = event_dispatcher

    def commit_execution(self, order, broker_order_id: str, outcome: ExecutionOutcome, broker_name: str, correlation_id: str = None) -> ExecutionReportContract:
        agg = self.repository.get_or_create(order.order_id, broker_order_id, order.symbol, order.quantity)
        
        total_filled = sum((f.quantity for f in outcome.fills), Decimal("0"))
        avg_price = (
            sum((f.quantity * f.price for f in outcome.fills), Decimal("0")) / total_filled
            if total_filled > 0 else Decimal("0")
        )

        temp_report = ExecutionReportContract(
            client_order_id=order.order_id,
            broker_order_id=broker_order_id,
            status=outcome.status,
            filled_quantity=total_filled,
            remaining_quantity=outcome.remaining_quantity,
            average_fill_price=avg_price,
            error_message=outcome.error_message,
            timestamp=outcome.execution_timestamp,
            broker_name=broker_name,
            correlation_id=correlation_id,
            version=agg.version + 1
        )

        new_version = agg.apply_report(temp_report)
        final_report = dataclasses.replace(temp_report, version=new_version)
        agg.reports[-1] = final_report

        events = []
        try:
            if total_filled > Decimal("0"):
                for fill in outcome.fills:
                    self.position_engine.apply_execution(order, fill.price, fill.quantity, fill.exchange_timestamp)
                    pos = self.position_engine.get_position(order.symbol)
                    if pos:
                        events.append(PositionUpdatedEvent(order.symbol, pos.quantity, pos.average_price, fill.exchange_timestamp))

                self.account_engine.apply_execution(final_report, order.side, avg_price, total_filled)
                acc = self.account_engine.get_account_contract()
                events.append(AccountUpdatedEvent(acc.cash_balance, outcome.execution_timestamp))
                
                if total_filled < order.quantity:
                    events.append(PartialFillEvent(order.order_id, total_filled, avg_price, outcome.execution_timestamp))
                else:
                    events.append(FillReceivedEvent(order.order_id, total_filled, avg_price, outcome.execution_timestamp))

            if final_report.status == OrderStatus.SUBMITTED:
                events.append(OrderSubmittedEvent(order.order_id, broker_order_id, outcome.execution_timestamp))
            elif final_report.status == OrderStatus.OPEN:
                events.append(OrderAcceptedEvent(order.order_id, broker_order_id, outcome.execution_timestamp))
            elif final_report.status == OrderStatus.REJECTED:
                events.append(OrderRejectedEvent(order.order_id, final_report.error_message or "Unknown", outcome.execution_timestamp))

            if final_report.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                events.append(OrderCompletedEvent(order.order_id, final_report.status, outcome.execution_timestamp))

            # Record into Event Store & Dispatch
            for ev in events:
                self.event_store.append(order.order_id, type(ev).__name__, ev, outcome.execution_timestamp)
                if self.event_dispatcher:
                    self.event_dispatcher.emit(ev)

            return final_report
        except Exception as e:
            raise RuntimeError(f"Commit engine failed for order {order.order_id}: {e}") from e

    def commit_cancel(self, client_order_id: str, broker_name: str, timestamp: int) -> ExecutionReportContract:
        agg = self.repository.get(client_order_id)
        latest = agg.get_latest() if agg else None
        
        if not latest or latest.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            raise ValueError(f"Cannot cancel order {client_order_id} in terminal status {latest.status if latest else 'UNKNOWN'}.")

        temp_report = ExecutionReportContract(
            client_order_id=client_order_id,
            broker_order_id=latest.broker_order_id,
            status=OrderStatus.CANCELLED,
            filled_quantity=agg.filled_qty,
            remaining_quantity=agg.remaining_qty,
            average_fill_price=agg.average_price,
            error_message=None,
            timestamp=timestamp,
            broker_name=broker_name,
            correlation_id=latest.correlation_id,
            version=agg.version + 1
        )
        new_version = agg.apply_report(temp_report)
        final_report = dataclasses.replace(temp_report, version=new_version)
        agg.reports[-1] = final_report

        cancel_ev = OrderCancelledEvent(client_order_id, timestamp)
        completed_ev = OrderCompletedEvent(client_order_id, OrderStatus.CANCELLED, timestamp)

        self.event_store.append(client_order_id, "OrderCancelledEvent", cancel_ev, timestamp)
        self.event_store.append(client_order_id, "OrderCompletedEvent", completed_ev, timestamp)

        if self.event_dispatcher:
            self.event_dispatcher.emit(cancel_ev)
            self.event_dispatcher.emit(completed_ev)

        return final_report
