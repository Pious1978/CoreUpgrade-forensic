from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class AuditMetadata:
    """
    Immutable static audit discovery contract featuring institutional 
    execution characteristics, criticality levels, and ownership.
    """
    audit_id: str
    name: str
    category: str
    version: str = "1.0"
    tags: Tuple[str, ...] = field(default_factory=tuple)
    dependencies: Tuple[str, ...] = field(default_factory=tuple)
    
    # Execution characteristics for intelligent scheduling & concurrency
    parallel_safe: bool = True
    estimated_runtime_seconds: int = 60
    criticality: str = "NORMAL"  # e.g., LOW, NORMAL, HIGH, CRITICAL
    
    # Enterprise ownership
    owner_team: str = "AuditEngineering"
