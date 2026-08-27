"""
Plugin Adapter for Gate 2: Contract Integrity
"""
import os
import ast
from control_plane.gate_interface import AuditGate
from core.artifact_envelope import AuditArtifactEnvelope

class Gate2Plugin(AuditGate):
    gate_id = "Gate 2 – Contract Integrity"
    layer = "Platform Integrity"

    def execute(self) -> bool:
        # Re-use your AST validation logic from gate2_contracts.py
        # For demonstration of orchestration integration:
        from audits.gate2_contracts import ContractIntegrityGate
        gate = ContractIntegrityGate()
        # Capture check counts or status
        try:
            gate.run_all_checks()
            self.passed = gate.passed_checks == gate.total_checks
        except Exception:
            self.passed = False
        return self.passed

    def get_artifact(self) -> AuditArtifactEnvelope:
        return AuditArtifactEnvelope.create(
            artifact_type="gate2_contract_report",
            generated_by="Gate2Plugin",
            payload={"status": "PASS" if getattr(self, 'passed', False) else "FAIL"}
        )
