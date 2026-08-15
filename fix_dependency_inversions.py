import os

print("--- REMEDIATING DEPENDENCY INVERSIONS ---")

# 1. Clean core/artifact_store.py (Remove governance/audit leakage)
artifact_store_code = '''"""
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
'''
os.makedirs("core", exist_ok=True)
with open(os.path.join("core", "artifact_store.py"), "w", encoding="utf-8") as f:
    f.write(artifact_store_code)
print("Refactored: core/artifact_store.py (Purged audit imports)")

# 2. Clean core/scoring_engine.py (Remove audits.findings leakage)
scoring_engine_code = '''"""
Core Scoring Engine: Pure mathematical calculation layer.
Returns raw numeric metrics; zero knowledge of audit findings.
"""
from typing import Dict, Any

class ScoringEngine:
    def calculate_score(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """Calculates raw alpha score and confidence metrics."""
        raw_val = metrics.get("sharpe", 1.0) * 50.0
        score = max(0.0, min(100.0, raw_val))
        
        return {
            "score": float(score),
            "confidence": 0.85,
            "status": "VALID" if score > 50.0 else "SUBOPTIMAL"
        }
'''
with open(os.path.join("core", "scoring_engine.py"), "w", encoding="utf-8") as f:
    f.write(scoring_engine_code)
print("Refactored: core/scoring_engine.py (Purged audit imports)")
