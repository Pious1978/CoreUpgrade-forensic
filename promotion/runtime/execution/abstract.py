from abc import ABC, abstractmethod
from typing import Any, Type
from ...domain.context import PromotionContext
from ...domain.result_types import PromotionResult

class Executor(ABC):
    @abstractmethod
    def execute(self, source: Any, target_type: Type[Any], context: PromotionContext) -> PromotionResult: pass
