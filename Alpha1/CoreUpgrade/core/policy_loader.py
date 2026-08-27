from pathlib import Path
import yaml
from typing import Dict, Any
from core.policy_validator import PolicyValidator


class PolicyLoader:
    """Loads and validates institutional governance and decision thresholds from YAML."""
    
    def __init__(self, policy_path: str = "config/governance_policy.yaml"):
        self.policy_path = Path(policy_path)
        self.policy = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.policy_path.exists():
            data = {
                "policy": {
                    "approval": {"minimum_compliance_score": 90, "maximum_risk_score": 20},
                    "conditional": {"minimum_compliance_score": 80, "maximum_risk_score": 50},
                    "rejection": {"critical_findings_allowed": 0}
                }
            }
        else:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        policy_section = data.get("policy", {})
        PolicyValidator.validate(policy_section)
        return policy_section

    def get(self) -> Dict[str, Any]:
        return self.policy
