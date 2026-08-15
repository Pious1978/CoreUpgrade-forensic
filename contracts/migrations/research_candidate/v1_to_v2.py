"""
Research Candidate Migration (v1 to v2)

Handles data structure transformations from schema version '1.0' to '2.0'.
"""

from typing import Dict, Any


def migrate_v1_to_v2(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upgrades historical research candidate payloads to support v2 schema updates.
    """
    # Example migration logic: mapping legacy field names or injecting defaults
    migrated = dict(payload)
    if "discovery_score" in migrated and "signal_strength" not in migrated:
        migrated["signal_strength"] = migrated.pop("discovery_score")
    return migrated
