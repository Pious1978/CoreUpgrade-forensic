from typing import List, Type, Dict, Any
from ..contracts.empirical_theorem import EmpiricalTheorem
from ..contracts.empirical_result import ExecutionEmpiricalResult
from .theorem_executor import TheoremExecutor
from .proof_builder import ProofBuilder
from .certificate_issuer import CertificateIssuer

class CertificationRuntime:
    def __init__(self, registry_manifest_hash: str, theorems: List[Type[EmpiricalTheorem]]):
        self.registry_manifest_hash = registry_manifest_hash
        self.theorems = theorems

    def execute_certification(self, severity_override: str = "INFO") -> ExecutionEmpiricalResult:
        results: Dict[str, Any] = {}
        diagnostics: Dict[str, Any] = {}
        execution_order: List[str] = []

        # Deterministic sorting of theorems by identifier to guarantee runtime stability
        sorted_theorems = sorted(self.theorems, key=lambda t: t.id)

        for theorem in sorted_theorems:
            execution_order.append(theorem.id)
            sub_res = TheoremExecutor.execute(theorem)
            results[theorem.id] = sub_res.get("status", "SUCCESS")
            diagnostics[theorem.id] = sub_res.get("diagnostics", {"execution_ms": 1.0})

        proof_payload = ProofBuilder.build_proof_payload(
            registry_manifest_hash=self.registry_manifest_hash,
            results=results,
            execution_order=execution_order,
            theorems=sorted_theorems
        )

        master_hash = ProofBuilder.compute_master_hash(proof_payload)

        certificate = CertificateIssuer.issue(
            master_proof_hash=master_hash,
            proof_payload=proof_payload,
            diagnostics=diagnostics,
            execution_order=execution_order,
            results=results,
            severity=severity_override
        )

        return certificate