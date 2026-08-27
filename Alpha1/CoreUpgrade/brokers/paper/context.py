from dataclasses import dataclass
from brokers.enums import Environment, BrokerId

@dataclass(frozen=True, slots=True)
class ExecutionContext:
    broker_id: BrokerId
    environment: Environment
    account_id: str
    tenant_id: str | None = None
