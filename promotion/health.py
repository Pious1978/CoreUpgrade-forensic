from dataclasses import dataclass, field
from typing import Dict, Any
from .graph import PromotionGraph
from .exceptions import PromotionError

@dataclass(frozen=True)
class PromotionHealthReport:
    graph: str
    policies: str
    dependencies: str
    storage: str
    security: str
    details: Dict[str, Any] = field(default_factory=dict)

class PromotionHealthChecker:
    @staticmethod
    def verify(graph: PromotionGraph) -> PromotionHealthReport:
        if not graph.is_frozen():
            raise PromotionError("Health check failed: PromotionGraph is not frozen.")
        graph.validate()
        
        all_edges = list(graph.edges())
        if not all_edges:
            raise PromotionError("Health check failed: PromotionGraph contains zero registered edges.")

        policy_count = 0
        for _, edge in all_edges:
            if edge.policy is None:
                raise PromotionError(f"Health check failed: Promoter '{edge.promoter.__name__}' is missing an assigned policy.")
            policy_count += 1

        return PromotionHealthReport(
            graph="PASS",
            policies="PASS",
            dependencies="NOT_IMPLEMENTED",
            storage="UNKNOWN",
            security="UNKNOWN",
            details={
                "graph_edges": len(all_edges),
                "policy_bindings": policy_count,
                "dependency_check": "NOT_IMPLEMENTED"
            }
        )
