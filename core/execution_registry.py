import importlib
from typing import Any
from core.control_definition import ControlDefinition

class ExecutionRegistry:
    """Dynamically resolves and invokes control executors via configuration mappings."""

    @staticmethod
    def execute(control: ControlDefinition) -> Any:
        if not control.executor_module or not control.executor_function:
            raise AttributeError(f"Control '{control.id}' lacks valid executor configuration.")

        try:
            module = importlib.import_module(control.executor_module)
            executor = getattr(module, control.executor_function)
        except (ImportError, AttributeError) as e:
            raise RuntimeError(f"Failed to load execution target for control '{control.id}': {e}")

        return executor()
