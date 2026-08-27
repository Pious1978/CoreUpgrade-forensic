from abc import ABC, abstractmethod
from ..graph import PromotionGraph

class HealthProbe(ABC):
    @abstractmethod
    def check(self) -> str: pass

class GraphProbe(HealthProbe):
    def __init__(self, graph: PromotionGraph) -> None:
        self.graph = graph
    def check(self) -> str:
        return "PASS" if self.graph.is_frozen() else "FAIL"

class StorageProbe(HealthProbe):
    def check(self) -> str:
        return "PASS" # Stub for persistence integration
