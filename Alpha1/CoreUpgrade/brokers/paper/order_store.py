from typing import Dict, Tuple, Optional
from .execution_aggregate import ExecutionAggregate
from .contracts import ExecutionReportContract

class OrderStore:
    def __init__(self):
        self._aggregates: Dict[str, ExecutionAggregate] = {}

    def get_or_create(self, client_order_id: str, broker_order_id: str, symbol: str, requested_qty: Decimal) -> ExecutionAggregate:
        if client_order_id not in self._aggregates:
            self._aggregates[client_order_id] = ExecutionAggregate(
                client_order_id=client_order_id,
                broker_order_id=broker_order_id,
                symbol=symbol,
                requested_qty=requested_qty
            )
        return self._aggregates[client_order_id]

    def get(self, client_order_id: str) -> Optional[ExecutionAggregate]:
        return self._aggregates.get(client_order_id)

    def commit_report(self, report: ExecutionReportContract):
        agg = self._aggregates.get(report.client_order_id)
        if agg:
            agg.apply_report(report)
