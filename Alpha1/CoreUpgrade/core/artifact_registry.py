"""
Centralized Artifact Registry: Handles persistence, loading, verification, 
and querying of unified AuditArtifactEnvelopes.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from core.artifact_envelope import AuditArtifactEnvelope

class ArtifactRegistry:
    def __init__(self, base_dir: str = "event_store/artifacts"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def register_artifact(self, gate_name: str, envelope: AuditArtifactEnvelope) -> str:
        """Saves an envelope into event_store/artifacts/{gate_name}/."""
        gate_dir = os.path.join(self.base_dir, gate_name)
        os.makedirs(gate_dir, exist_ok=True)
        
        filename = f"{envelope.artifact_type}_{envelope.artifact_id}.json"
        filepath = os.path.join(gate_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(envelope.to_dict(), f, indent=4)
        
        return filepath

    def load_artifact(self, filepath: str) -> Optional[AuditArtifactEnvelope]:
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AuditArtifactEnvelope(**data)

    def verify_artifact(self, filepath: str) -> bool:
        """Cryptographically verifies payload and artifact fingerprints against tampering."""
        envelope = self.load_artifact(filepath)
        if not envelope:
            return False
        
        # 1. Recompute payload fingerprint
        payload_str = json.dumps(envelope.payload, sort_keys=True, default=str)
        expected_p_fp = hashlib.sha256(payload_str.encode()).hexdigest()[:12]
        
        # 2. Recompute artifact fingerprint
        meta_string = (
            f"{envelope.artifact_type}:{envelope.artifact_id}:{envelope.schema_version}:"
            f"{envelope.generated_by}:{envelope.platform_version}:{envelope.architecture_version}:{expected_p_fp}"
        )
        expected_a_fp = hashlib.sha256(meta_string.encode()).hexdigest()[:12]
        
        return (envelope.payload_fingerprint == expected_p_fp) and (envelope.artifact_fingerprint == expected_a_fp)

    def list_artifacts(self, gate_name: Optional[str] = None) -> List[str]:
        target_dir = os.path.join(self.base_dir, gate_name) if gate_name else self.base_dir
        if not os.path.exists(target_dir):
            return []
        
        artifact_paths = []
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".json"):
                    artifact_paths.append(os.path.join(root, file))
        return sorted(artifact_paths)

    def find_latest(self, gate_name: str, artifact_type: str) -> Optional[AuditArtifactEnvelope]:
        paths = self.list_artifacts(gate_name)
        matching = []
        for p in paths:
            env = self.load_artifact(p)
            if env and env.artifact_type == artifact_type:
                matching.append((env.generated_at, p))
        
        if not matching:
            return None
        
        matching.sort(key=lambda x: x[0], reverse=True)
        return self.load_artifact(matching[0][1])
