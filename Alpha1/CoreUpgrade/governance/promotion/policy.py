from typing import List
from research.adapter import ResearchCandidate
from .evaluator import MultiFactorPromotionEvaluator
from .result import PromotionResult

class ResearchPromotionPolicyEngine:
    def __init__(self, evaluator: MultiFactorPromotionEvaluator = None):
        self.evaluator = evaluator or MultiFactorPromotionEvaluator()

    def review_candidates(self, candidates: List[ResearchCandidate]) -> List[PromotionResult]:
        return [self.evaluator.evaluate_candidate(c) for c in candidates]

    def select_best_promoted(self, candidates: List[ResearchCandidate]) -> ResearchCandidate:
        results = self.review_candidates(candidates)
        
        # Print audit table
        print("\n--- VSC 2.2 Multi-Factor Governance Audit ---")
        for res in results:
            status = "APPROVED ✅" if res.approved else "REJECTED ❌"
            print(f"[{status}] Symbol: {res.symbol}")
            for r in res.reasons:
                print(f"    └─ {r}")
        print("-" * 50)

        approved_symbols = {res.symbol for res in results if res.approved}
        valid_candidates = [c for c in candidates if c.symbol in approved_symbols]

        if not valid_candidates:
            raise ValueError("Zero research candidates passed the VSC 2.2 multi-factor governance gates.")

        # Sort by conviction score * confidence
        valid_candidates.sort(key=lambda c: (c.score * c.confidence), reverse=True)
        return valid_candidates[0]
