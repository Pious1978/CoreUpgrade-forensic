from typing import Optional, Any
from .repository import PromotionRepository
from .transaction_manager import AbstractTransactionManager

class PostgresRepository(PromotionRepository):
    def __init__(self, tx_manager: AbstractTransactionManager) -> None:
        self.tx_manager = tx_manager

    def save_contract(self, contract: Any) -> None:
        pass

    def load_contract(self, contract_id: str) -> Optional[Any]:
        return None
