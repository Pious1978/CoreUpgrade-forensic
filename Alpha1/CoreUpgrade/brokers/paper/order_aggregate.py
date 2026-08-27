from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from decimal import Decimal
from .contracts import ExecutionReportContract

@dataclass
class OrderAggregate:
    client_order_id: str
    broker_order_id: str
    symbol: str
    initial_quantity: Decimal
    _history: List[ExecutionReportContract] = field(default_factory=list)

    @property
    def current_state(self) -> OrderStatus:
        return self._history[-1].status if self._history else OrderStatus.SUBMITTED

    @property
    def filled_quantity(self) -> Decimal:
        return sum((report.filled_quantity for report in self._history), Decimal("0"))

    @property
    def remaining_quantity(self) -> Decimal:
        latest = self._history[-1] if self._history else None
        return latest.remaining_quantity if latest else self.initial_quantity

    def add_report(self, report: ExecutionReportContract):
        self._history.append(report)

    def get_history(self) -> Tuple[ExecutionReportContract, ...]:
        return tuple(self._history)

    def get_latest(self) -> Optional[ExecutionReportContract]:
        return self._history[-1] if self._history else None
