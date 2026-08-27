from abc import ABC, abstractmethod
from typing import List
from research.adapter import ResearchCandidate

class BaseScanner(ABC):
    @abstractmethod
    def scan(self) -> List[ResearchCandidate]:
        pass
