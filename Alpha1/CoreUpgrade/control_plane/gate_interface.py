"""
Audit Gate Interface: Universal plugin specification for all platform integrity, 
data, and research validation gates.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from core.artifact_envelope import AuditArtifactEnvelope

class AuditGate(ABC):
    gate_id: str
    layer: str
    version: str = "1.0.0"
    dependencies: List[str] = []

    @abstractmethod
    def execute(self) -> bool:
        """
        Executes the audit checks. 
        Returns True if all checks pass, False otherwise.
        """
        pass

    @abstractmethod
    def get_artifact(self) -> Optional[AuditArtifactEnvelope]:
        """
        Retrieves the standardized artifact envelope produced during execution.
        """
        pass
