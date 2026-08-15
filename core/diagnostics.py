from typing import Dict, Any
from core.audit_registry import registry
from core.audit_config import config

class FrameworkDiagnostics:
    """Performs self-diagnostics on framework registry, configuration, and runtime environment."""

    @staticmethod
    def run_diagnostics() -> Dict[str, Any]:
        issues = []
        try:
            layers = registry.get_execution_layers()
            module_count = sum(len(layer) for layer in layers)
        except Exception as e:
            module_count = 0
            issues.append(f"Registry DAG resolution failed: {e}")

        return {
            "status": "HEALTHY" if not issues else "DEGRADED",
            "registered_modules_count": module_count,
            "configuration_loaded": config is not None,
            "issues": issues
        }
