"""
Canonical Serializer

Transforms contract instances into deterministic, normalized dictionary structures 
specifically formatted for cryptographic hash digest computations.
"""

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Dict, Any, FrozenSet
from uuid import UUID


CANONICAL_EXCLUDED_FIELDS: FrozenSet[str] = frozenset({
    "payload_hash",
    "_sealed",
    "_integrity_verified",
    "capabilities",
})


def to_canonical_dict(contract: Any) -> Dict[str, Any]:
    """
    Converts any contract instance into its canonical dictionary form, 
    normalizing datetimes, UUIDs, and nested mappings.
    """
    def unfreeze(val: Any) -> Any:
        if isinstance(val, (MappingProxyType, dict)) or (hasattr(val, "items") and not isinstance(val, (datetime, UUID))):
            return {k: unfreeze(v) for k, v in val.items()}
        if isinstance(val, (tuple, list)):
            return [unfreeze(v) for v in val]
        if isinstance(val, frozenset):
            return [unfreeze(v) for v in val]
        return val

    serialized_created_at = contract.created_at.isoformat(timespec="seconds").replace("+00:00", "Z")

    return {
        "domain": contract.domain,
        "contract_id": str(contract.contract_id),
        "contract_type": contract.contract_type,
        "contract_version": contract.contract_version,
        "schema_name": contract.schema_name,
        "schema_version": contract.schema_version,
        "producer": contract.producer,
        "producer_version": contract.producer_version,
        "environment": contract.environment.value,
        "hash_algorithm": contract.hash_algorithm.value,
        "event_type": contract.event_type,
        "state": contract.state.value,
        "trust_level": contract.trust_level.value,
        "state_history": unfreeze(contract.state_history),
        "trust_history": unfreeze(contract.trust_history),
        "created_at": serialized_created_at,
        "parent_contract_id": str(contract.parent_contract_id) if contract.parent_contract_id else None,
        "correlation_id": str(contract.correlation_id) if contract.correlation_id else None,
        "causation_id": str(contract.causation_id) if contract.causation_id else None,
        "metadata": unfreeze(contract.metadata),
        "payload": unfreeze(contract.contract_payload()),
    }
