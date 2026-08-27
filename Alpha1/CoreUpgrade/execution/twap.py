import random
from typing import List

class TWAPExecution:
    """
    Generates Time-Weighted Average Price (TWAP) schedules with randomized interval sizing.
    """
    
    def __init__(self, intervals: int = 10, randomize: bool = True):
        self.intervals = intervals
        self.randomize = randomize

    def generate_schedule(self, total_quantity: float) -> List[float]:
        base_qty = total_quantity / self.intervals
        if not self.randomize:
            return [round(base_qty, 2)] * self.intervals
            
        weights = [random.uniform(0.6, 1.4) for _ in range(self.intervals)]
        total_weight = sum(weights)
        return [round(total_quantity * (w / total_weight), 2) for w in weights]
