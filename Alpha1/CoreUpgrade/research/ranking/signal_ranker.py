from typing import List
from research.adapter import ResearchCandidate

class SignalRanker:
    def rank(self, candidates: List[ResearchCandidate]) -> ResearchCandidate:
        # Selects the highest-conviction candidate based on score and confidence
        sorted_candidates = sorted(candidates, key=lambda c: (c.score * c.confidence), reverse=True)
        if not sorted_candidates:
            raise ValueError("No research candidates produced by scanners.")
        return sorted_candidates[0]
