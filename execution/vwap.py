from typing import List

class VWAPExecution:
    """
    Generates Volume-Weighted Average Price (VWAP) execution schedules 
    based on intraday volume curves.
    """
    
    def __init__(self, volume_curve: List[float] = None):
        # Standard institutional intraday volume curve profile (~13 half-hour blocks)
        self.volume_curve = volume_curve or [0.12, 0.09, 0.07, 0.06, 0.05, 0.05, 0.05, 0.06, 0.07, 0.09, 0.12, 0.14, 0.04]
        total = sum(self.volume_curve)
        self.normalized_curve = [v / total for v in self.volume_curve]

    def generate_schedule(self, total_quantity: float) -> List[float]:
        return [round(total_quantity * weight, 2) for weight in self.normalized_curve]
