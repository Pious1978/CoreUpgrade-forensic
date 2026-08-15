from typing import List, Dict
from research.adapter import ResearchCandidate

class ConvictionWeightedAllocator:
    """Calculates deterministic portfolio weights based on conviction (score * confidence) with position capping."""
    def __init__(self, capital_base: float = 1000000.0, max_position_weight: float = 0.40):
        self.capital_base = capital_base
        self.max_position_weight = max_position_weight

    def allocate(self, approved_candidates: List[ResearchCandidate]) -> Dict[str, float]:
        if not approved_candidates:
            return {}
        
        # Calculate raw conviction scores
        convictions = {c.symbol: (c.score * c.confidence) for c in approved_candidates}
        total_conviction = sum(convictions.values())
        
        if total_conviction == 0:
            equal_wt = 1.0 / len(approved_candidates)
            return {c.symbol: min(equal_wt, self.max_position_weight) for c in approved_candidates}

        # Proportional allocation
        raw_weights = {symbol: (conv / total_conviction) for symbol, conv in convictions.items()}
        
        capped_weights = {}
        excess = 0.0
        uncapped_symbols = []

        for symbol, weight in raw_weights.items():
            if weight > self.max_position_weight:
                excess += (weight - self.max_position_weight)
                capped_weights[symbol] = self.max_position_weight
            else:
                capped_weights[symbol] = weight
                uncapped_symbols.append(symbol)

        # Redistribute excess proportionally to uncapped symbols
        if excess > 0 and uncapped_symbols:
            uncapped_total = sum(raw_weights[s] for s in uncapped_symbols)
            if uncapped_total > 0:
                for symbol in uncapped_symbols:
                    addition = excess * (raw_weights[symbol] / uncapped_total)
                    new_wt = capped_weights[symbol] + addition
                    capped_weights[symbol] = min(new_wt, self.max_position_weight)

        return {s: round(w, 2) for s, w in capped_weights.items()}
