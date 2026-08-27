"""
Core Artifact Store: Pure persistence layer. 
Zero knowledge of governance or audits.
"""
import json
import hashlib
from typing import Dict, Any, Optional

class ArtifactStore:
    def __init__(self):
        self._store: Dict[str, str] = {}

    def save(self, artifact_id: str, payload: Dict[str, Any]) -> str:
        """Saves payload, computes cryptographic hash, and returns it."""
        serialized = json.dumps(payload, sort_keys=True, default=str)
        content_hash = hashlib.sha256(serialized.encode()).hexdigest()[:12]
        self._store[artifact_id] = serialized
        return content_hash

    def load(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Loads and parses stored artifact payload."""
        if artifact_id not in self._store:
            return None
        return json.loads(self._store[artifact_id])
