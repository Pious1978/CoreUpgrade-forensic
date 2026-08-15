import importlib
from typing import Dict, Type
from pathlib import Path
import yaml
from core.audit_base import BaseAudit
from core.exceptions import RegistryValidationError
from core.logger import get_logger

logger = get_logger("control_execution_registry")


class ControlExecutionRegistry:
    """
    Dynamic plugin loader mapping external control identifiers to executable
    audit modules via python module inspection and importlib.
    """

    def __init__(self, config_path: str = "config/controls.yaml"):
        self.config_path = Path(config_path)
        self.bindings: Dict[str, Type[BaseAudit]] = {}
        self._load_bindings()

    def _load_bindings(self) -> None:
        if not self.config_path.exists():
            logger.warning("Controls config path not found for execution bindings", extra={"path": str(self.config_path)})
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        controls_cfg = data.get("controls", {})
        for control_id, cfg in controls_cfg.items():
            executor_path = cfg.get("executor")
            if not executor_path:
                continue
            
            try:
                audit_class = self._resolve_class(executor_path)
                self.bindings[control_id] = audit_class
                logger.info("Successfully bound control to audit execution class", extra={"control_id": control_id, "executor": executor_path})
            except Exception as e:
                logger.error("Failed to resolve control execution module", extra={"control_id": control_id, "executor": executor_path, "error": str(e)})
                raise RegistryValidationError(f"Failed to bind control '{control_id}' to executor '{executor_path}': {str(e)}") from e

    def _resolve_class(self, classpath: str) -> Type[BaseAudit]:
        if "." not in classpath:
            raise ImportError(f"Invalid module classpath format: {classpath}")
        
        module_name, class_name = classpath.rsplit(".", 1)
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        
        if not issubclass(cls, BaseAudit):
            raise TypeError(f"Class {classpath} is not a valid subclass of BaseAudit")
        
        return cls

    def get_audit_class(self, control_id: str) -> Type[BaseAudit]:
        if control_id not in self.bindings:
            raise KeyError(f"No execution binding registered for control ID: {control_id}")
        return self.bindings[control_id]
