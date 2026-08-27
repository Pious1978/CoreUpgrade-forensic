from abc import ABC, abstractmethod
from typing import Any, Callable, List, Tuple
from .context import PromotionContext
from .result import PromotionResult
from .metadata import PromotionMetadata
from .trace import PromotionTrace
from .status import PromotionStatus

class BasePromotionService(ABC):
    """Pure business logic promoter providing reusable template method execution pipelines."""

    def __init__(self) -> None:
        self.before_validation_hooks: List[Callable[[Any, PromotionContext], None]] = []
        self.after_validation_hooks: List[Callable[[Any, PromotionContext], None]] = []
        self.before_transition_hooks: List[Callable[[Any, PromotionContext], None]] = []
        self.after_transition_hooks: List[Callable[[Any, PromotionContext], None]] = []
        self.before_commit_hooks: List[Callable[[Tuple[Any, ...], PromotionContext], None]] = []
        self.after_commit_hooks: List[Callable[[Tuple[Any, ...], PromotionContext], None]] = []

    def _execute_pipeline(
        self,
        source_contract: Any,
        context: PromotionContext,
        metadata: PromotionMetadata
    ) -> Tuple[PromotionResult, Tuple[Any, ...]]:
        trace = PromotionTrace()
        span = trace.start_span("promotion_pipeline", {"source": type(source_contract).__name__})

        for hook in self.before_validation_hooks:
            hook(source_contract, context)

        self.validate_source(source_contract, context)
        self.validate_capabilities(source_contract, context)
        policy_result = self.evaluate_policy(source_contract, context)

        for hook in self.after_validation_hooks:
            hook(source_contract, context)

        decision = self.create_decision(source_contract, policy_result, context)
        target = self.create_target(source_contract, decision, context)
        self.validate_target(target, context)

        for hook in self.before_transition_hooks:
            hook(source_contract, context)

        transitioned_source = self.transition_source(source_contract, context)

        for hook in self.after_transition_hooks:
            hook(transitioned_source, context)

        audit = self.create_audit(source_contract, target, decision, context)

        finalized_metadata = metadata.finalize()
        result = PromotionResult(
            source=source_contract,
            transitioned_source=transitioned_source,
            decision=decision,
            target=target,
            audit=audit,
            metadata=finalized_metadata,
            trace=PromotionTrace(root_span=span),
            status=PromotionStatus.COMMITTED,
            metrics={"status": "COMMITTED", "idempotency_key": context.idempotency_key},
            duration_ms=finalized_metadata.duration_ms,
            success=True
        )

        contracts_tuple = (source_contract, transitioned_source, decision, target, audit)
        return result, contracts_tuple

    @abstractmethod
    def validate_source(self, source: Any, context: PromotionContext) -> None: pass
    @abstractmethod
    def validate_capabilities(self, source: Any, context: PromotionContext) -> None: pass
    @abstractmethod
    def evaluate_policy(self, source: Any, context: PromotionContext) -> Any: pass
    @abstractmethod
    def create_decision(self, source: Any, policy_result: Any, context: PromotionContext) -> Any: pass
    @abstractmethod
    def create_target(self, source: Any, decision: Any, context: PromotionContext) -> Any: pass
    @abstractmethod
    def validate_target(self, target: Any, context: PromotionContext) -> None: pass
    @abstractmethod
    def transition_source(self, source: Any, context: PromotionContext) -> Any: pass
    @abstractmethod
    def create_audit(self, source: Any, target: Any, decision: Any, context: PromotionContext) -> Any: pass
