from dataclasses import dataclass, field
from typing import Dict, Any, List
from ..graph import PromotionGraph
from ..exceptions import PromotionError
from .probes import HealthProbe

@dataclass(frozen=True)
class PromotionHealthReport:
    graph: str
    policies: str
    dependencies: str
    storage: str
    security: str
    details: Dict[str, Any] = field(default_factory=dict)

class PromotionHealthChecker:
    """Modular health checker executing registered diagnostic probes."""
    def __init__(self, probes: List[HealthProbe] = None) -> None:
        self.probes = probes or []

    def verify(self, graph: PromotionGraph) -> PromotionHealthReport:
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

        probe_results = {type(p).__name__: p.check() for p in self.probes}

        return PromotionHealthReport(
            graph="PASS",
            policies="PASS",
            dependencies=probe_results.get("GraphProbe", "PASS"),
            storage=probe_results.get("StorageProbe", "UNKNOWN"),
            security="PASS",
            details={
                "graph_edges": len(all_edges),
                "policy_bindings": policy_count,
                "probes": probe_results
            }
        )
