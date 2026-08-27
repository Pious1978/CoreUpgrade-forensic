from typing import Dict, Any
from core.exceptions import RegistryValidationError
from core.logger import get_logger

logger = get_logger("policy_validator")


class PolicyValidator:
    """Validates governance policy schemas to prevent silent default misconfigurations."""
    
    @staticmethod
    def validate(policy_data: Dict[str, Any]) -> None:
        required_sections = ["approval", "conditional", "rejection"]
        for section in required_sections:
            if section not in policy_data:
                logger.error(f"Missing required policy section: {section}")
                raise RegistryValidationError(f"Missing required policy section: {section}")
        
        approval = policy_data["approval"]
        if "minimum_compliance_score" not in approval or "maximum_risk_score" not in approval:
            raise RegistryValidationError("Approval policy section must specify minimum_compliance_score and maximum_risk_score")
        
        conditional = policy_data["conditional"]
        if "minimum_compliance_score" not in conditional or "maximum_risk_score" not in conditional:
            raise RegistryValidationError("Conditional policy section must specify minimum_compliance_score and maximum_risk_score")
        
        rejection = policy_data["rejection"]
        if "critical_findings_allowed" not in rejection:
            raise RegistryValidationError("Rejection policy section must specify critical_findings_allowed")
        
        logger.info("Governance policy schema validated successfully")
