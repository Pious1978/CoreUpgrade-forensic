"""
Certification Engine (Pure Decision Engine)

Responsible for evaluating audit run execution evidence against an institutional
CertificationPolicy to render a final, tamper-evident certification verdict.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Any, Optional
from control_plane.certification_policy import CertificationPolicy
from control_plane.certification_result import CertificationResult


class CertificationEngine:

    def __init__(self, policy: Optional[CertificationPolicy] = None):
        """
        Initializes the engine with a configurable institutional policy.
        """
        self.policy = policy or CertificationPolicy()

    def evaluate(
        self,
        registered_gate_count: int,
        executed_gate_count: int,
        execution_results: List[Any]
    ) -> CertificationResult:
        """
        Pure decision function: Evaluates execution evidence against policy 
        following strict evidence-trust ordering without mutating state.
        """
        all_passed = True
        for result in execution_results:
            status = getattr(result, "status", None)
            if status != "PASS":
                all_passed = False
                break

        failure_reason = None
        master_verdict = "REJECTED"

        # ---------------------------------------------------------
        # Evidence Trust & Policy Enforcement Order
        # ---------------------------------------------------------
        if registered_gate_count < self.policy.minimum_gate_count:
            print("[ERROR] Certification attempted with insufficient registered gates.")
            failure_reason = (
                "Certification blocked: "
                f"Registered gates ({registered_gate_count}) below minimum threshold ({self.policy.minimum_gate_count})."
            )
        elif executed_gate_count == 0:
            print("[ERROR] Certification attempted with zero executed gates.")
            failure_reason = "Certification blocked: Zero validation gates were executed."
        elif len(execution_results) != executed_gate_count:
            print("[ERROR] Certification evidence count mismatch detected.")
            failure_reason = (
                "Certification blocked: "
                f"Execution evidence count ({len(execution_results)}) does not match executed gate count ({executed_gate_count})."
            )
        elif self.policy.block_on_execution_mismatch and (executed_gate_count != registered_gate_count):
            print("[ERROR] Certification execution count mismatch detected.")
            failure_reason = (
                "Certification blocked: "
                f"Registered gates ({registered_gate_count}) != Executed gates ({executed_gate_count})."
            )
        else:
            master_verdict = "CERTIFIED" if all_passed else "REJECTED"
            if not all_passed:
                failure_reason = "Certification blocked: One or more gates failed or returned non-passing status."

        # Generate unique institutional certification ID and ISO timestamp
        utc_now = datetime.now(timezone.utc)
        cert_id = f"CERT-{utc_now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        issued_at_str = utc_now.isoformat()

        return CertificationResult(
            certification_id=cert_id,
            issued_at=issued_at_str,
            policy_version=self.policy.policy_version,
            master_verdict=master_verdict,
            registered_gate_count=registered_gate_count,
            executed_gate_count=executed_gate_count,
            failure_reason=failure_reason,
            execution_results=tuple(execution_results)
        )
