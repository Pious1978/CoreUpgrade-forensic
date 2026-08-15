from dataclasses import dataclass, field
from typing import Type, Dict, Tuple, Set, List, Any, Iterator, FrozenSet
from types import MappingProxyType
from .exceptions import RegistryFrozenError
from .graph_validator import GraphValidator

@dataclass(frozen=True)
class PromotionEdge:
    """Single canonical metadata container with immutable FrozenSets."""
    promoter: Type[Any]
    policy: Type[Any] | None = None
    guards: Tuple[Type[Any], ...] = ()
    capabilities: FrozenSet[str] = frozenset()
    permissions: FrozenSet[str] = frozenset()
    priority: int = 100
    enabled: bool = True
    deprecated: bool = False
    min_framework_version: str = "2.0"
    tags: Tuple[str, ...] = ("production",)

class PromotionGraph:
    """Directed workflow graph featuring sealed mapping proxies and immutable raw edge returns."""
    
    def __init__(self) -> None:
        self._graph: Dict[Tuple[Type[Any], Type[Any]], PromotionEdge] = {}
        self._frozen: bool = False

    def add_edge(self, source_type: Type[Any], target_type: Type[Any], edge: PromotionEdge) -> None:
        if self._frozen:
            raise RegistryFrozenError("Cannot modify promotion graph; graph is frozen.")
        self._graph[(source_type, target_type)] = edge

    def get_edge(self, source_type: Type[Any], target_type: Type[Any]) -> PromotionEdge:
        key = (source_type, target_type)
        if key not in self._graph:
            raise KeyError(f"No promotion edge registered for contract classes '{source_type.__name__}' -> '{target_type.__name__}'.")
        return self._graph[key]

    def edges(self) -> Iterator[Tuple[Tuple[Type[Any], Type[Any]], PromotionEdge]]:
        return iter(self._graph.items())

    def nodes(self) -> Set[Type[Any]]:
        return {src for src, _ in self._graph.keys()}.union({tgt for _, tgt in self._graph.keys()})

    def raw_edges_list(self) -> Tuple[Tuple[Type[Any], Type[Any]], ...]:
        return tuple(self._graph.keys())

    def validate(self) -> None:
        GraphValidator.validate(self.nodes(), list(self.raw_edges_list()))

    def topological_sort(self) -> List[Type[Any]]:
        return GraphValidator.topological_sort(self.nodes(), list(self.raw_edges_list()))

    def roots(self) -> Set[Type[Any]]:
        return GraphValidator.roots(self.nodes(), list(self.raw_edges_list()))

    def leaves(self) -> Set[Type[Any]]:
        return GraphValidator.leaves(self.nodes(), list(self.raw_edges_list()))

    def orphans(self) -> Set[Type[Any]]:
        return GraphValidator.orphans(self.nodes(), list(self.raw_edges_list()))

    def freeze(self) -> None:
        self._graph = MappingProxyType(dict(self._graph))
        self._frozen = True

    def is_frozen(self) -> bool:
        return self._frozen

    def clear(self) -> None:
        if self._frozen:
            raise RegistryFrozenError("Cannot clear frozen graph.")
        self._graph.clear()

default_registry = PromotionGraph()

def promotion(
    source: Type[Any],
    target: Type[Any],
    policy: Type[Any] | None = None,
    guards: Tuple[Type[Any], ...] = (),
    capabilities: Set[str] | FrozenSet[str] | None = None,
    permissions: Set[str] | FrozenSet[str] | None = None,
    priority: int = 100,
    tags: Tuple[str, ...] = ("production",)
):
    def decorator(cls):
        edge = PromotionEdge(
            promoter=cls,
            policy=policy,
            guards=guards,
            capabilities=frozenset(capabilities or ()),
            permissions=frozenset(permissions or ()),
            priority=priority,
            tags=tags
        )
        default_registry.add_edge(source, target, edge)
        return cls
    return decorator
