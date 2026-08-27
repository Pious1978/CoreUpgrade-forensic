"""
Research Signal Migration: v1.0 to v2.0

Upgrades legacy research signal payloads to comply with v2 schema structures.
"""

from typing import Dict, Any
from contracts.migrations.registry import MigrationRegistry


def migrate_v1_to_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms v1 research signal payload fields into v2 specifications 
    (e.g., restructuring scoring metrics or normalizing risk flags).
    """
    migrated = dict(payload)
    migrated["schema_version"] = "2.0"
    
    # Example migration transformation
    if "discovery_score" in migrated and "confidence_index" not in migrated:
        migrated["confidence_index"] = migrated.pop("discovery_score")

    return migrated


# Register migration path
MigrationRegistry.register(
    domain="research",
    schema_name="research_signal",
    from_version="1.0",
    to_version="2.0",
    migration_func=migrate_v1_to_v2,
)
