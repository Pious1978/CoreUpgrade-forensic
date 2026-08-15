from abc import ABC, abstractmethod
from typing import Optional

from brokers.enums import BrokerId
from brokers.paper.capabilities import BrokerCapabilities
from contracts.broker.account_contract import AccountContract
from contracts.broker.order_contract import OrderContract
from contracts.broker.position_contract import PositionContract
from execution.contracts.execution_report_contract import ExecutionReportContract

class BrokerInterface(ABC):
    """
    Stable execution boundary.

    All broker adapters (Paper, Zerodha, IBKR, Alpaca, etc.)
    implement this interface.

    Implementations must never expose broker-native payloads.
    All returned objects must be immutable execution contracts.
    """

    @property
    @abstractmethod
    def broker_id(self) -> BrokerId:
        """Returns the unique BrokerId enum identifier."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> BrokerCapabilities:
        """Returns the capability profile supported by the broker adapter."""
        ...

    @abstractmethod
    def submit_order(
        self,
        order: OrderContract,
    ) -> ExecutionReportContract:
        """Submits an order to the execution engine or external broker."""
        ...

    @abstractmethod
    def cancel_order(
        self,
        client_order_id: str,
    ) -> ExecutionReportContract:
        """Requests cancellation of an active order by client order identifier."""
        ...

    @abstractmethod
    def get_order_status(
        self,
        client_order_id: str,
    ) -> ExecutionReportContract | None:
        """Retrieves the latest execution state for an order, or None if not found."""
        ...

    @abstractmethod
    def get_positions(
        self,
    ) -> tuple[PositionContract, ...]:
        """Returns an immutable tuple of current open positions."""
        ...

    @abstractmethod
    def get_account_balance(
        self,
    ) -> AccountContract:
        """Returns the current account balance and buying power snapshot."""
        ...

    @abstractmethod
    def get_execution_history(
        self,
        account_id: str,
        limit: int = 100,
    ) -> tuple[ExecutionReportContract, ...]:
        """Returns an immutable history of execution reports/fills for a given account."""
        ...
