from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class IndicatorExpression:
    name: str
    operation: str
    periods: int  # Negative periods indicate future-looking shifts (e.g., -1)

@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    strategy_id: str
    name: str
    indicators: tuple[IndicatorExpression, ...]
