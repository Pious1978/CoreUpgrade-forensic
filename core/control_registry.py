from typing import Dict, List, Any
from core.control_validator import ControlValidator
from core.control_definition import ControlDefinition

class ControlRegistry:
    """Manages the lifecycle and storage of validated, immutable control definitions."""

    def __init__(self, raw_controls: List[Dict[str, Any]]):
        self._controls: Dict[str, ControlDefinition] = {}
        for raw_control in raw_controls:
            self.register(raw_control)

    def register(self, raw_control: Dict[str, Any]) -> None:
        # Step 1: Validate external definition via trust gate
        ControlValidator.validate(raw_control)

        # Step 2: Convert into immutable/frozen object
        control = ControlDefinition(
            id=raw_control["id"],
            name=raw_control["name"],
            category=raw_control["category"],
            weight=raw_control["weight"],
            owner_team=raw_control["owner_team"],
            owner_role=raw_control["owner_role"],
            remediation_sla_hours=raw_control["remediation_sla_hours"],
            executor_module=raw_control.get("executor_module"),
            executor_function=raw_control.get("executor_function")
        )

        if control.id in self._controls:
            raise ValueError(f"Control ID collision detected: duplicate control id '{control.id}'")

        self._controls[control.id] = control

    def get(self, control_id: str) -> ControlDefinition:
        if control_id not in self._controls:
            raise KeyError(f"Control definition not found in registry: '{control_id}'")
        return self._controls[control_id]

    def list_all(self) -> List[ControlDefinition]:
        return list(self._controls.values())
