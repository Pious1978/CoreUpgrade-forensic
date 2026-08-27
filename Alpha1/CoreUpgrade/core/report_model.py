from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class AuditReport:
    """Unified schema container for final institutional audit reporting."""
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)
    governance: Dict[str, Any] = field(default_factory=dict)
    scoring: Dict[str, Any] = field(default_factory=dict)
    module_results: List[Dict[str, Any]] = field(default_factory=list)
    category_breakdowns: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    summary: str = ""
