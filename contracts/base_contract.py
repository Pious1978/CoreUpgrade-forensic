from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Dict, Any, Optional

@dataclass(frozen=True)
class BaseContract:
    immutable_id: UUID = field(default_factory=uuid4)
    parent_contract_id: Optional[UUID] = None
    root_contract_id: UUID = field(default_factory=uuid4)
    correlation_id: UUID = field(default_factory=uuid4)
    contract_type: str = "BaseContract"
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    producer: str = "SYSTEM"
    schema_version: int = 1
    trust_level: str = "RAW"
    lifecycle_state: str = "INITIALIZED"
    contract_hash: str = "sha256-placeholder"
    signature: str = "sig-placeholder"
    metadata: Dict[str, Any] = field(default_factory=dict)
