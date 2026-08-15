from abc import ABC, abstractmethod
from typing import Optional, Any

class PromotionRepository(ABC):
    @abstractmethod
    def save_contract(self, contract: Any) -> None: pass

    @abstractmethod
    def load_contract(self, contract_id: str) -> Optional[Any]: pass
