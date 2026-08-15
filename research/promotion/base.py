from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple
from research.adapter import ResearchCandidate

@dataclass(frozen=True)
class PromotionDecision:
    candidate: ResearchCandidate
    is_promoted: bool
    reasons: List[str]

class BasePromotionPolicy(ABC):
    @abstractmethod
    def evaluate(self, candidate: ResearchCandidate) -> PromotionDecision:
        pass
