from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AuditExecutor(ABC):
    """
    Abstract Base Class enforcing a uniform contract for all audit modules.
    Prevents schema drift and runtime contract violations.
    """

    @abstractmethod
    def execute(self) -> List[Dict[str, Any]]:
        """
        Executes the specific audit checks and returns a list of raw finding dictionaries
        adhering strictly to the finding contract specification.
        """
        pass
