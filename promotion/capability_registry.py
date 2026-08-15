from typing import Type, Set, Dict, Any

class CapabilityRegistry:
    """Dynamic registry mapping contract types to required institutional execution capabilities."""

    def __init__(self) -> None:
        self._requirements: Dict[Type[Any], Set[str]] = {}

    def register(self, contract_type: Type[Any], capabilities: Set[str]) -> None:
        self._requirements[contract_type] = capabilities

    def get_required(self, contract_type: Type[Any]) -> Set[str]:
        return self._requirements.get(contract_type, set())
