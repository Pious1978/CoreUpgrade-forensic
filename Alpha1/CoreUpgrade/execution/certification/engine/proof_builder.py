"""
Proof Builder Engine

Authority:
    Execution Layer Deterministic Cryptographic Proof Generation
"""
import subprocess
from typing import Dict, Any, Tuple, Type, List
from research.governance.serialization import CanonicalSerializer
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem

class ProofBuilder:
    @staticmethod
    def get_git_commit() -> str:
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            return commit.decode("utf-8").strip()
        except Exception:
            return "UNKNOWN_GIT_COMMIT"

    @classmethod
    def build_proof(
        cls,
        master_id: str,
        master_version: str,
        engine_version: str,
        schema_version: str,
        proof_schema: str,
        hash_algorithm: str,
        all_certified: bool,
        registry_manifest_hash: str,
        registry_fingerprint: str,
        dependency_graph_hash: str,
        sorted_theorems: Tuple[Type[EmpiricalTheorem], ...],
        results: Dict[str, Dict[str, Any]],
        execution_order: List[str]
    ) -> Tuple[str, str, Dict[str, Any]]:
        sorted_results = {
            k: results[k]
            for k in sorted(results.keys())
        }

        theorem_implementations = {
            t.id: getattr(t, "implementation_hash", CanonicalSerializer.hash(t.__name__))
            for t in sorted_theorems
        }

        expected_self_proof = {
            "theorem_id": master_id,
            "version": master_version,
            "proof_schema": proof_schema,
            "registry_fingerprint": registry_fingerprint,
            "registry_manifest_hash": registry_manifest_hash,
            "engine_version": engine_version,
            "hash_algorithm": hash_algorithm,
        }

        provenance = {
            "git_commit": cls.get_git_commit(),
            "engine_manifest_hash": CanonicalSerializer.digest({"version": engine_version}),
            "registry_manifest_hash": registry_manifest_hash,
            "registry_fingerprint": registry_fingerprint,
            "dependency_graph_hash": dependency_graph_hash,
            "theorem_implementations": theorem_implementations,
            "serializer_version": "1.0.0",
        }

        proof_payload = {
            "schema_version": schema_version,
            "proof_schema": proof_schema,
            "hash_algorithm": hash_algorithm,
            "certified": all_certified,
            "theorem_id": master_id,
            "version": master_version,
            "engine_version": engine_version,
            "registry_fingerprint": registry_fingerprint,
            "dependency_graph_hash": dependency_graph_hash,
            "execution_order": execution_order,
            "provenance": provenance,
            "orchestrator_self_proof": expected_self_proof,
            "results": sorted_results,
        }

        master_proof_hash = CanonicalSerializer.digest(proof_payload)
        return master_proof_hash, registry_fingerprint, provenance
```[cite: 35]