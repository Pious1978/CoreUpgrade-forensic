from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from decimal import Decimal
from .contracts import ExecutionReportContract

@dataclass
class ExecutionAggregate:
    client_order_id: str
    broker_order_id: str
    symbol: str
    requested_qty: Decimal
    filled_qty: Decimal = Decimal("0")
    remaining_qty: Decimal = field(init=False)
    average_price: Decimal = Decimal("0")
    status: OrderStatus = OrderStatus.SUBMITTED
    version: int = 0
    reports: List[ExecutionReportContract] = field(default_factory=list)

    def __post_init__(self):
        self.remaining_qty = self.requested_qty

    def apply_report(self, report: ExecutionReportContract) -> int:
        if report.version <= self.version and self.version != 0:
            raise ValueError(f"Concurrency conflict: aggregate version {self.version} >= report version {report.version}")
        
        self.version = self.version + 1
        self.status = report.status
        self.filled_qty = report.filled_quantity
        self.remaining_qty = report.remaining_quantity
        self.average_price = report.average_fill_price
        self.reports.append(report)
        return self.version

    def get_history(self) -> Tuple[ExecutionReportContract, ...]:
        return tuple(self.reports)

    def get_latest(self) -> Optional[ExecutionReportContract]:
        return self.reports[-1] if self.reports else None
