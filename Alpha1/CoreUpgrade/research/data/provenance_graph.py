# research/data/provenance_graph.py
import dataclasses
from typing import Tuple, Any, Dict
from research.governance.serialization import CanonicalSerializer

@dataclasses.dataclass(frozen=True)
class TemporalDomain:
    """
    Interval arithmetic for temporal provenance.
    Uses strictly integers to prevent floating-point serialization drift.
    """
    min_lag: int
    max_lag: int

    def combine(self, other: 'TemporalDomain') -> 'TemporalDomain':
        """Used for arithmetic (+, -, *, /) and logic (>, <, ==)."""
        return TemporalDomain(
            min_lag=min(self.min_lag, other.min_lag),
            max_lag=max(self.max_lag, other.max_lag)
        )

    def shift(self, periods: int) -> 'TemporalDomain':
        """
        Pandas shift(1) means row T gets T-1's data.
        So lag shifts by -periods.
        """
        return TemporalDomain(
            min_lag=self.min_lag - int(periods),
            max_lag=self.max_lag - int(periods)
        )

    def rolling(self, window: int, center: bool = False) -> 'TemporalDomain':
        """
        rolling(5) looks back 4 periods + current period.
        If center=True, it looks forward by (window-1)//2 periods.
        """
        window_int = int(window)
        forward_shift = (window_int - 1) // 2 if center else 0
        lookback = (window_int - 1) - forward_shift
        
        return TemporalDomain(
            min_lag=self.min_lag - lookback,
            max_lag=self.max_lag + forward_shift
        )
    
    def __str__(self):
        return f"[{self.min_lag}, {self.max_lag}]"


@dataclasses.dataclass(frozen=True)
class FeatureNode:
    """
    The Merkle-DAG node representing a specific computation in the research pipeline.
    Frozen, canonical, and cryptographically verified.
    """
    name: str
    operation: str
    domain: TemporalDomain
    parents: Tuple['FeatureNode', ...]
    metadata: Tuple[Tuple[str, Any], ...]  # Tuple of Tuples enforces hashability and strict ordering
    schema_version: str = "v2.1"
    node_hash: str = dataclasses.field(init=False)

    def __post_init__(self):
        # Generate parent hashes strictly from the Merkle tree lineage
        parent_hashes = tuple(p.node_hash for p in self.parents)
        
        # Build a deterministic payload for the CanonicalSerializer.
        # We do not hash the 'name' field, ensuring that identical math operations 
        # (e.g., intermediate variables named 'x' vs 'y') resolve to the exact same hash.
        payload = {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "metadata": self.metadata,
            "domain": {
                "min_lag": self.domain.min_lag, 
                "max_lag": self.domain.max_lag
            },
            "parent_hashes": parent_hashes
        }
        
        computed_hash = CanonicalSerializer.hash(payload, algorithm="SHA-256")
        
        # Bypass frozen constraint exactly once during initialization
        object.__setattr__(self, 'node_hash', computed_hash)


class FeatureNodeDeserializer:
    """
    Supports THEOREM-REPLAY-001 by reconstructing the immutable FeatureNode 
    graph from cold storage or a JSON artifact.
    """
    
    @classmethod
    def load(cls, serialized_dag: Dict[str, Any]) -> FeatureNode:
        # Reconstruct TemporalDomain
        domain_data = serialized_dag.get('domain', {})
        domain = TemporalDomain(
            min_lag=int(domain_data.get('min_lag', 0)),
            max_lag=int(domain_data.get('max_lag', 0))
        )
        
        # Reconstruct parents recursively
        parents_data = serialized_dag.get('parents', [])
        parents = tuple(cls.load(p) for p in parents_data)
        
        # Reconstruct metadata as Tuple[Tuple[str, Any]]
        metadata_data = serialized_dag.get('metadata', [])
        # Coerce any lists back into tuples to maintain immutability
        metadata = tuple((str(k), v) for k, v in metadata_data)
        
        # Instantiate the node. 
        # The __post_init__ hook will automatically recalculate the Merkle hash.
        node = FeatureNode(
            name=str(serialized_dag.get('name', '')),
            operation=str(serialized_dag.get('operation', '')),
            domain=domain,
            parents=parents,
            metadata=metadata,
            schema_version=str(serialized_dag.get('schema_version', 'v2.1'))
        )
        
        # Cryptographic verification: Ensure the recomputed Merkle hash 
        # perfectly matches the fingerprint saved in the artifact.
        stored_hash = serialized_dag.get('node_hash')
        if stored_hash and stored_hash != node.node_hash:
            raise ValueError(
                f"Provenance Corruption Detected! Recomputed hash for node '{node.name}' "
                f"({node.node_hash}) does not match the stored artifact fingerprint ({stored_hash})."
            )
            
        return node
