from dataclasses import dataclass
from uuid import UUID
from brokers.enums import Environment, BrokerId, ExecutionMode
from execution.capabilities.account_capabilities import AccountCapabilities

@dataclass(frozen=True, slots=True)
class ExecutionContext:
    execution_id: UUID
    broker_id: BrokerId
    environment: Environment
    mode: ExecutionMode
    account_id: str
    account_capabilities: AccountCapabilities
    tenant_id: str | None = None
