import subprocess
import hashlib
import json
from typing import Dict, Any, List, Type
from ..contracts.empirical_theorem import EmpiricalTheorem

class ProofBuilder:
    @staticmethod
    def get_git_commit() -> str:
        """Addresses Issue 6: True reproducible git provenance."""
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            ).decode("utf-8").strip()
        except Exception:
            return "UNKNOWN_COMMIT"

    @staticmethod
    def build_proof_payload(
        registry_manifest_hash: str,
        results: Dict[str, Any],
        execution_order: List[str],
        theorems: List[Type[EmpiricalTheorem]]
    ) -> Dict[str, Any]:
        # Addresses Issue 1: Deterministic dictionary sorting before hashing
        sorted_results = {
            k: results[k]
            for k in sorted(results.keys())
        }

        # Addresses Issue 7: Inclusion of theorem implementation identity fingerprints
        theorem_implementations = {
            t.id: t.implementation_hash
            for t in sorted(theorems, key=lambda x: x.id)
        }

        proof_payload = {
            "registry_manifest_hash": registry_manifest_hash,
            "git_commit": ProofBuilder.get_git_commit(),
            "results": sorted_results,
            "execution_order": execution_order,  # Addresses Issue 5: Proven execution sequence
            "theorem_implementations": theorem_implementations,
        }
        return proof_payload

    @staticmethod
    def compute_master_hash(proof_payload: Dict[str, Any]) -> str:
        payload_bytes = json.dumps(proof_payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()