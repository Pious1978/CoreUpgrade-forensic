# portfolio/construction/constraint_registry.py
import hashlib
import dataclasses
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Tuple, Dict, Type

from portfolio.contracts.constraint_contract import PortfolioConstraint
from portfolio.contracts.portfolio_certificate import TargetWeight, ConstraintEvaluation
from portfolio.universe.metadata_provider import PointInTimeMetadata
from portfolio.construction.constraints import (
    AbstractConstraintEvaluator,
    MaxPositionSizeEvaluator,
    MaxSectorExposureEvaluator,
    MaxParticipationRateEvaluator
)

@dataclasses.dataclass(frozen=True)
class EvaluatorRegistration:
    constraint_type: str
    version: str
    evaluator_cls: Type[AbstractConstraintEvaluator]
    
    @property
    def implementation_hash(self) -> str:
        payload = f"{self.constraint_type}_{self.version}_{self.evaluator_cls.__name__}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

class VersionedConstraintRegistry:
    """
    Immutable registry mapping constraint types to versioned, hash-locked evaluators.
    Enforces 'Fail-Closed' behavior for unknown or unversioned rules.
    """
    def __init__(self):
        self._registry: Dict[str, EvaluatorRegistration] = {}
        
        # Register standard frozen evaluators with explicit versioning
        self.register("MAX_POSITION_SIZE", "1.0.0", MaxPositionSizeEvaluator)
        self.register("MAX_SECTOR_EXPOSURE", "1.0.0", MaxSectorExposureEvaluator)
        self.register("MAX_PARTICIPATION_RATE", "1.0.0", MaxParticipationRateEvaluator)

    def register(self, constraint_type: str, version: str, cls: Type[AbstractConstraintEvaluator]):
        self._registry[constraint_type] = EvaluatorRegistration(
            constraint_type=constraint_type,
            version=version,
            evaluator_cls=cls
        )

    def get_evaluator(self, constraint_ type: str) -> AbstractConstraintEvaluator:
        registration = self._registry.get(constraint_type)
        if not registration:
            # FAIL CLOSED: Unknown constraints are strictly prohibited
            raise KeyError(
                f"FATAL GOVERNANCE BREACH: Unrecognized constraint type '{constraint_type}' encountered. "
                f"Evaluation halted (Fail-Closed policy)."
            )
        return registration.evaluator_cls()

    def get_implementation_hash(self, constraint_type: str) -> str:
        registration = self._registry.get(constraint_type)
        if not registration:
            raise KeyError(f"No registration found for constraint type: {constraint_type}")
        return registration.implementation_hash
