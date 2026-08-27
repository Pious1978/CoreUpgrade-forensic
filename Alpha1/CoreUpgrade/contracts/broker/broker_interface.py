from abc import ABC, abstractmethod
from typing import List
from contracts.broker.order_contract import OrderContract
from contracts.broker.broker_response_contract import BrokerResponseContract
from contracts.broker.position_contract import PositionContract
from contracts.broker.account_contract import AccountContract

class BrokerInterface(ABC):
    @abstractmethod
    def submit_order(self, order: OrderContract) -> BrokerResponseContract:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> BrokerResponseContract:
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> BrokerResponseContract:
        pass

    @abstractmethod
    def get_positions(self) -> List[PositionContract]:
        pass

    @abstractmethod
    def get_account_balance(self) -> AccountContract:
        pass
