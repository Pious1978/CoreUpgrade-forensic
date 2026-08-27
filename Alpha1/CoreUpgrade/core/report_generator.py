import json
import os
from pathlib import Path
from typing import Dict, Any

class ReportGenerator:
    """
    Serializes governance runtime execution results into structured compliance artifacts.
    """

    def __init__(self, base_output_dir: str = "audit_artifacts"):
        self.base_output_dir = Path(base_output_dir)

    def generate_package(self, run_id: str, run_results: Dict[str, Any]) -> str:
        run_dir = self.base_output_dir / f"RUN-{run_id}"
        evidence_dir = run_dir / "evidence"
        
        # Ensure directory structure exists
        run_dir.mkdir(parents=True, exist_ok=True)
        evidence_dir.mkdir(parents=True, exist_ok=True)

        manifest = run_results["manifest"]
        findings = run_results["findings"]

        # 1. Write execution manifest
        with open(run_dir / "execution_manifest.json", "w") as f:
            json.dump(manifest.__dict__, f, indent=4)

        # 2. Write policy hash proof
        with open(run_dir / "policy_hash.sha256", "w") as f:
            f.write(manifest.policy_hash)

        # 3. Write findings bundle
        findings_data = [f.__dict__ for f in findings]
        with open(run_dir / "findings.json", "w") as f:
            json.dump(findings_data, f, indent=4)

        # 4. Write individual evidence files
        for finding in findings:
            evidence_file = evidence_dir / f"{finding.finding_id}.json"
            with open(evidence_file, "w") as f:
                json.dump(finding.evidence, f, indent=4)

        return str(run_dir)
