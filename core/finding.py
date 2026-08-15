from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class Finding:
    """Immutable representation of a normalized compliance or security finding."""
    finding_id: str
    control_id: str
    severity: str
    title: str
    description: str
    evidence: Dict[str, Any]
    detected_at: str
