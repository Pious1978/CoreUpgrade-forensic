from dataclasses import dataclass, field
from typing import Type, Set, Tuple, Any
from .graph import PromotionGraph

@dataclass(frozen=True)
class PromotionExecutionPlan:
    """Pre-execution blueprint detailing structural paths, policies, guards, capabilities, and permissions."""
    source_type: Type[Any]
    target_type: Type[Any]
    promoter: Type[Any]
    policy: Type[Any] | None
    guards: Tuple[Type[Any], ...] = ()
    required_capabilities: Set[str] = field(default_factory=set)
    required_permissions: Set[str] = field(default_factory=set)
    version: str = "2.6.0"

class ExecutionPlanBuilder:
    @staticmethod
    def explain(source_type: Type[Any], target_type: Type[Any], graph: PromotionGraph) -> PromotionExecutionPlan:
        edge = graph.get_edge(source_type, target_type)
        return PromotionExecutionPlan(
            source_type=source_type,
            target_type=target_type,
            promoter=edge.promoter,
            policy=edge.policy,
            guards=edge.guards,
            required_capabilities=edge.capabilities,
            required_permissions=edge.permissions
        )
