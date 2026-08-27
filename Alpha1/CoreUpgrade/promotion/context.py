from dataclasses import dataclass, field
from typing import Optional, Tuple
from uuid import UUID, uuid4
import time

@dataclass(frozen=True)
class PermissionsContext:
    roles: Tuple[str, ...] = ()
    scopes: Tuple[str, ...] = ()

@dataclass(frozen=True)
class RiskContext:
    max_exposure: float = 0.25
    desk_limit: float = 1000000.0

@dataclass(frozen=True)
class PortfolioContext:
    book_id: str = "DEFAULT"
    strategy_code: str = "DEFAULT"

@dataclass(frozen=True)
class ExecutionContext:
    venue: str = "DEFAULT_VENUE"
    routing_algorithm: str = "TWAP"

@dataclass(frozen=True)
class PromotionContext:
    """Immutable, strongly-typed institutional promotion execution context."""
    actor: str
    desk: str
    strategy: str
    approval_level: str
    tenant: str = "DEFAULT"
    environment: str = "PRODUCTION"
    trigger: str = "EVENT"
    trace_id: UUID = field(default_factory=uuid4)
    correlation_id: Optional[UUID] = field(default_factory=uuid4)
    workflow_id: Optional[UUID] = None
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))
    request_timestamp: float = field(default_factory=time.time)
    max_retries: int = 3
    permissions: PermissionsContext = field(default_factory=PermissionsContext)
    risk_context: RiskContext = field(default_factory=RiskContext)
    portfolio_context: PortfolioContext = field(default_factory=PortfolioContext)
    execution_context: ExecutionContext = field(default_factory=ExecutionContext)
