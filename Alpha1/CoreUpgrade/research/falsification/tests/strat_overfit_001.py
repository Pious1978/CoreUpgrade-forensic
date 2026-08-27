# research/falsification/tests/strat_overfit_001.py
from research.falsification.harness import AbstractFalsificationHarness
from research.falsification.poisons import DirectShiftPoison, DeepNestedPoison

class StratOverfit001(AbstractFalsificationHarness):
    @property
    def test_id(self) -> str:
        return "STRAT-OVERFIT-001"

    @property
    def poisons(self) -> tuple:
        return (
            DirectShiftPoison(),
            DeepNestedPoison(),
            # Add future temporal poisons here...
        )
        
    @property
    def negative_controls(self) -> tuple:
        return (
            lambda tdf: tdf['close'].shift(1).rolling(252).mean(),
            lambda tdf: tdf['volume'].expanding().max() - tdf['close'].ewm(span=10).mean(),
        )
