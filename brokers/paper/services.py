from dataclasses import dataclass
from .clock import Clock
from .id_generator import OrderIdGenerator
from .execution_repository import ExecutionRepository
from .commit_engine import ExecutionCommitEngine
from .query_service import ExecutionQueryService
from .position_engine import PositionEngine
from .account_engine import AccountEngine
from .event_store import EventStore

@dataclass(frozen=True)
class ExecutionServices:
    clock: Clock
    id_generator: OrderIdGenerator
    repository: ExecutionRepository
    commit_engine: ExecutionCommitEngine
    query_service: ExecutionQueryService
    position_engine: PositionEngine
    account_engine: AccountEngine
    event_store: EventStore
