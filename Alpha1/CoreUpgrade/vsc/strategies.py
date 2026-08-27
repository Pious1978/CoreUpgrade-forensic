class EqualWeightAllocator:
    def allocate(self, target_weight: float) -> float:
        return target_weight

class MaxWeightRiskPolicy:
    def __init__(self, max_cap: float = 0.20):
        self.max_cap = max_cap

    def apply(self, weight: float) -> float:
        return min(weight, self.max_cap)

class PositionSizer:
    def calculate_quantity(self, approved_weight: float, capital: float = 100_000.0, price: float = 175.00) -> float:
        allocated_capital = capital * approved_weight
        return allocated_capital / price
