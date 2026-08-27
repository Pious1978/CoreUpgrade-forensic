from typing import List
from research.adapter import ResearchCandidate
from .allocator import ConvictionWeightedAllocator

class PortfolioConstructionEngine:
    def __init__(self, allocator: ConvictionWeightedAllocator = None):
        self.allocator = allocator or ConvictionWeightedAllocator()

    def construct(self, approved_candidates: List[ResearchCandidate]):
        allocations = self.allocator.allocate(approved_candidates)
        
        print("\n--- VSC 3.0 Portfolio Construction Allocation Table ---")
        print(f"{'Symbol':<10} | {'Allocation Weight':<18} | {'Capital Allocation (₹)':<22}")
        print("-" * 58)
        for symbol, weight in allocations.items():
            allocated_capital = weight * self.allocator.capital_base
            print(f"{symbol:<10} | {weight * 100:>16.1f}% | ₹{allocated_capital:>20,.2f}")
        print("-" * 58)

        return allocations
