from dataclasses import dataclass
from typing import Optional, final, override

from brokers.broker_interface import BrokerInterface
from brokers.enums import BrokerId, Environment
from brokers.paper.context import ExecutionContext
from brokers.paper.capabilities import BrokerCapabilities
from execution.application_service import ExecutionApplicationService
from contracts.broker.account_contract import AccountContract
from contracts.broker.order_contract import OrderContract
from contracts.broker.position_contract import PositionContract
from execution.contracts.execution_report_contract import ExecutionReportContract

@final
@dataclass(frozen=True, slots=True, kw_only=True)
class PaperBroker(BrokerInterface):
    app_service: ExecutionApplicationService
    context: ExecutionContext

    def __post_init__(self) -> None:
        if self.context.environment not in {Environment.PAPER, Environment.SIMULATION}:
            raise ValueError(
                f"PaperBroker governance guard violation: Requires {Environment.PAPER} or {Environment.SIMULATION}, "
                f"got {self.context.environment}."
            )

    @override
    @property
    def broker_id(self) -> BrokerId:
        return BrokerId.PAPER

    @override
    @property
    def capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            supports_cancel=True,
            supports_shorting=True,
            supports_options=False,
            supports_margin=True,
            supports_fractional=False,
            supports_stop_orders=True,
        )

    @override
    def submit_order(
        self,
        order: OrderContract,
    ) -> ExecutionReportContract:
        return self.app_service.submit_order(order)

    @override
    def cancel_order(
        self,
        client_order_id: str,
    ) -> ExecutionReportContract:
        return self.app_service.cancel_order(client_order_id)

    @override
    def get_order_status(
        self,
        client_order_id: str,
    ) -> ExecutionReportContract | None:
        return self.app_service.get_order_status(client_order_id)

    @override
    def get_positions(
        self,
    ) -> tuple[PositionContract, ...]:
        return tuple(self.app_service.get_positions())

    @override
    def get_account_balance(
        self,
    ) -> AccountContract:
        return self.app_service.get_account_balance()

    @override
    def get_execution_history(
        self,
        account_id: str,
        limit: int = 100,
    ) -> tuple[ExecutionReportContract, ...]:
        return self.app_service.get_order_history(account_id, limit)
