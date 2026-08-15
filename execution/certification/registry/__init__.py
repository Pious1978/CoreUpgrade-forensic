from typing import Tuple, Type

from execution.certification.contracts.empirical_theorem import EmpiricalTheorem

from execution.certification.theorem_eventstore_immutability_001 import EventStoreImmutabilityTheorem
from execution.certification.theorem_replay_determinism_001 import ReplayDeterminismTheorem
from execution.certification.theorem_empty_stream_001 import EmptyStreamReplayTheorem
from execution.certification.theorem_partial_fill_001 import PartialFillTheorem
from execution.certification.theorem_reconciliation_purity_001 import ReconciliationPurityTheorem


class ExecutionTheoremRegistry:
    """
    Pure structural registry holding the canonical tuple
    of boot-time certified empirical theorems.

    Runtime/per-event validators are invoked directly by their
    owning execution components and are intentionally excluded
    from this boot-time registry.
    """

    _REGISTRY: Tuple[Type[EmpiricalTheorem], ...] = (
        EventStoreImmutabilityTheorem,
        ReplayDeterminismTheorem,
        EmptyStreamReplayTheorem,
        PartialFillTheorem,
        ReconciliationPurityTheorem,
    )

    @classmethod
    def all(cls) -> Tuple[Type[EmpiricalTheorem], ...]:
        return cls._REGISTRY