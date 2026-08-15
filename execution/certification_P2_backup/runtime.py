"""
Execution Certification Runtime & State Lock

Authority:
    Execution Layer Admission Control & State Governance
"""
from enum import Enum, auto
from typing import Dict, Any, List, Type, Tuple
from dataclasses import dataclass
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
from execution.certification.theorem_execution_empirical_001 import ExecutionEmpiricalTheorem

class ExecutionRuntimeState(Enum):
    BOOTING = auto()
    CERTIFIED = auto()
    HALTED = auto()

class CertificationRuntimeStateStore:
    _state: ExecutionRuntimeState = ExecutionRuntimeState.BOOTING

    @classmethod
    def transition(cls, target_state: ExecutionRuntimeState):
        if cls._state == ExecutionRuntimeState.HALTED:
            raise RuntimeError("CRITICAL: Engine is permanently HALTED due to security violation or mutation attempt.")
        cls._state = target_state

    @classmethod
    def get_state(cls) -> ExecutionRuntimeState:
        return cls._state

    @classmethod
    def assert_certified(cls):
        if cls._state != ExecutionRuntimeState.CERTIFIED:
            raise RuntimeError(f"Security Violation: Engine state is {cls._state.name}, not CERTIFIED. Action blocked.")

class CertificationRuntime:
    """
    Decoupled runtime executor connecting the startup gate to the empirical orchestrator,
    enforcing runtime immutability locks.
    """
    @staticmethod
    def execute() -> Any:
        CertificationRuntimeStateStore.assert_certified()
        return ExecutionEmpiricalTheorem.verify()

    @staticmethod
    def validate_registry_explicit(available_classes: List[Type[EmpiricalTheorem]]) -> Tuple[Type[EmpiricalTheorem], ...]:
        return ExecutionEmpiricalTheorem.validate_registry_explicit(available_classes)