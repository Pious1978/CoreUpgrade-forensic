from dataclasses import dataclass, field
from uuid import UUID

@dataclass(frozen=True)
class AuditIdentity:
    actor: str
    desk: str
    tenant: str
    session_id: UUID
