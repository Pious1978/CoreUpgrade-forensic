# research/falsification/poisons.py
from abc import ABC, abstractmethod
from research.data.tracked_dataframe import TrackedDataFrame
from research.governance.artifacts import PoisonMetadata

class PoisonStrategy(ABC):
    @property
    @abstractmethod
    def metadata(self) -> PoisonMetadata: pass
    
    @abstractmethod
    def apply(self, tdf: TrackedDataFrame) -> TrackedDataFrame: pass

class DirectShiftPoison(PoisonStrategy):
    metadata = PoisonMetadata(
        id="POISON-001",
        category="Temporal",
        description="Injects strict T+1 future close",
        expected_theorems=("THEOREM-TEMPORAL-001",)
    )
    def apply(self, tdf: TrackedDataFrame):
        corrupted = tdf.copy()
        corrupted['close'] = corrupted['close'].shift(-1)
        return corrupted

class DeepNestedPoison(PoisonStrategy):
    metadata = PoisonMetadata(
        id="POISON-002",
        category="Temporal",
        description="Injects a future shift masked by a valid rolling mean and backward shift",
        expected_theorems=("THEOREM-TEMPORAL-001",)
    )
    def apply(self, tdf: TrackedDataFrame):
        corrupted = tdf.copy()
        corrupted['close'] = (
            corrupted['close'].shift(-5).rolling(10).mean().shift(2)
        )
        return corrupted
