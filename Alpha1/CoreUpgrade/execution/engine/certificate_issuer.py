from typing import Dict, Any, List
from types import MappingProxyType
from ..contracts.empirical_result import ExecutionEmpiricalResult, CertificationState

class CertificateIssuer:
    # Addresses Issue 3: 3-State/Granular Severity Dependency Policy Matrix
    DEPENDENCY_SEVERITY_POLICY = {
        "INFO": "ALLOW",
        "WARNING": "ALLOW",
        "ERROR": "BLOCK",
        "FATAL": "BLOCK"
    }

    @staticmethod
    def evaluate_policy(severity: str) -> str:
        return CertificateIssuer.DEPENDENCY_SEVERITY_POLICY.get(severity.upper(), "BLOCK")

    @classmethod
    def issue(
        cls,
        master_proof_hash: str,
        proof_payload: Dict[str, Any],
        diagnostics: Dict[str, Any],
        execution_order: List[str],
        results: Dict[str, Any],
        severity: str = "INFO"
    ) -> ExecutionEmpiricalResult:
        
        action = cls.evaluate_policy(severity)
        state = CertificationState.CERTIFIED if action == "ALLOW" else CertificationState.FAILED

        # Addresses Issue 4: Restoring deep MappingProxyType immutability for diagnostics
        frozen_diagnostics = MappingProxyType({
            k: MappingProxyType(v) if isinstance(v, dict) else v
            for k, v in diagnostics.items()
        })

        return ExecutionEmpiricalResult(
            state=state,
            master_proof_hash=master_proof_hash,
            proof_payload=proof_payload,
            diagnostics=frozen_diagnostics,
            execution_order=execution_order,
            results=results
        )