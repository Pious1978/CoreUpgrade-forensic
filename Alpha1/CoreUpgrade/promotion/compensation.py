from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

@dataclass(frozen=True)
class CompensationResult:
    action: str
    success: bool
    error: Optional[str] = None

class SagaRollbackError(Exception):
    def __init__(self, results: List[CompensationResult]) -> None:
        failed = [r for r in results if not r.success]
        super().__init__(f"Saga rollback failed for {len(failed)} action(s): {failed}")
        self.results = results

class CompensationAction(ABC):
    @abstractmethod
    def compensate(self, execution_id: UUID) -> None: pass

@dataclass(frozen=True)
class CompensationStep:
    """Higher priority compensations execute first during saga rollback."""
    action: CompensationAction
    priority: int

class SagaManager:
    def __init__(self, execution_id: UUID) -> None:
        self.execution_id = execution_id
        self._steps: List[CompensationStep] = []

    def add(self, action: CompensationAction, priority: int = 100) -> None:
        self._steps.append(CompensationStep(action=action, priority=priority))

    def rollback(self) -> None:
        sorted_steps = sorted(self._steps, key=lambda x: x.priority, reverse=True)
        results = []
        for step in sorted_steps:
            action_name = type(step.action).__name__
            try:
                step.action.compensate(self.execution_id)
                results.append(CompensationResult(action=action_name, success=True))
            except Exception as e:
                results.append(CompensationResult(action=action_name, success=False, error=str(e)))
        
        if any(not r.success for r in results):
            raise SagaRollbackError(results)
