from abc import ABC, abstractmethod
from typing import Any, Type
from ..context import PromotionContext
from ..result_types import PromotionResult

class AbstractPromotionExecutor(ABC):
    @abstractmethod
    def execute(self, source: Any, target_type: Type[Any], context: PromotionContext) -> PromotionResult: pass
