from typing import List
from research.adapter import ResearchCandidate
from .base import BasePromotionPolicy, PromotionDecision
from .threshold_policy import InstitutionalThresholdPolicy

class ResearchPromotionEngine:
    def __init__(self, policy: BasePromotionPolicy = None):
        self.policy = policy or InstitutionalThresholdPolicy()

    def filter_and_promote(self, candidates: List[ResearchCandidate]) -> List[PromotionDecision]:
        decisions = [self.policy.evaluate(c) for c in candidates]
        return decisions

    def get_top_promoted(self, candidates: List[ResearchCandidate]) -> ResearchCandidate:
        decisions = self.filter_and_promote(candidates)
        promoted = [d.candidate for d in decisions if d.is_promoted]
        
        if not promoted:
            raise ValueError("Zero research candidates satisfied the institutional promotion policy.")
        
        # Select best among promoted based on score * confidence
        promoted.sort(key=lambda c: (c.score * c.confidence), reverse=True)
        return promoted[0]
