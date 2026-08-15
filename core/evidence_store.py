from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import json
from core.fingerprint import FingerprintEngine

@dataclass(frozen=True)
class EvidenceArtifact:
    """Immutable representation of a stored cryptographic evidence package."""
    artifact_id: str
    finding_id: str
    location: str
    checksum: str
    created_at: str

class EvidenceStore:
    """Manages secure, immutable local file-system storage for audit and finding evidence."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store(self, finding_id: str, evidence: Dict[str, Any]) -> EvidenceArtifact:
        """
        Serializes raw evidence data to disk, generates a deterministic SHA-256 checksum,
        and returns an immutable evidence artifact tracker.
        """
        checksum = FingerprintEngine.generate_hash(evidence)
        filename = f"{finding_id}_{checksum[:12]}.json"
        path = self.base_path / filename

        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                evidence,
                file,
                indent=4,
                default=str
            )

        return EvidenceArtifact(
            artifact_id=checksum[:16],
            finding_id=finding_id,
            location=str(path),
            checksum=checksum,
            created_at=datetime.utcnow().isoformat()
        )
