from typing import Dict, Any

class VersionManager:
    """Handles schema compatibility checks and data payload migrations."""

    CURRENT_SCHEMA_VERSION = "2.0"

    @classmethod
    def migrate_payload(cls, payload: Dict[str, Any], from_version: str) -> Dict[str, Any]:
        if from_version == "1.0":
            payload["migrated_from"] = "1.0"
            payload["schema_version"] = cls.CURRENT_SCHEMA_VERSION
        return payload
