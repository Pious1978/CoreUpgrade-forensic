"""
Execution Result Contract (Production Hardened Event Record)

Records trade execution outcomes, institutional fill breakdowns, venue identities, 
latency metrics, and execution costs, inheriting directly from EventContract.
"""

from dataclasses import dataclass, field
from typing import Mapping, Any, Dict, ClassVar, Optional, Tuple
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contracts.event_contract import EventContract
from contracts.base_contract import Environment
from contracts.state import ContractState
from contracts.trust import TrustLevel
from contracts.execution.execution_status import ExecutionStatus
from contracts.freezer import freeze_metadata
from contracts.exceptions import ContractValidationError


@dataclass(frozen=True)
class ExecutionResultContract(EventContract):
    DOMAIN: ClassVar[str] = "execution"
    CONTRACT_TYPE: ClassVar[str] = "execution_result"
    SCHEMA_NAME: ClassVar[str] = "execution_result"
    SCHEMA_VERSION: ClassVar[str] = "1.0"

    execution_plan_id: UUID
    broker_name: str
    exchange: str
    venue: str
    broker_order_id: str
    status: ExecutionStatus
    filled_quantity: float
    average_price: float
    slippage_actual_bps: float
    fills: Tuple[Mapping[str, Any], ...]
    submitted_at: datetime
    exchange_acknowledged_at: datetime
    completed_at: datetime
    cost_breakdown: Mapping[str, Any]
    broker_response_payload: Mapping[str, Any]
    execution_timestamp: datetime

    def __post_init__(self):
        super().__post_init__()

        if not isinstance(self.execution_plan_id, UUID):
            raise ContractValidationError("Validation failed: execution_plan_id must be a UUID.")
        if not isinstance(self.broker_name, str) or not self.broker_name.strip():
            raise ContractValidationError("Validation failed: broker_name is mandatory.")
        if not isinstance(self.exchange, str) or not self.exchange.strip():
            raise ContractValidationError("Validation failed: exchange is mandatory.")
        if not isinstance(self.venue, str) or not self.venue.strip():
            raise ContractValidationError("Validation failed: venue is mandatory.")
        if not isinstance(self.broker_order_id, str) or not self.broker_order_id.strip():
            raise ContractValidationError("Validation failed: broker_order_id is mandatory.")

        if not isinstance(self.status, ExecutionStatus):
            try:
                object.__setattr__(self, "status", ExecutionStatus(self.status))
            except ValueError as e:
                raise ContractValidationError(f"Validation failed: invalid execution status '{self.status}'.") from e

        if not isinstance(self.filled_quantity, (int, float)) or self.filled_quantity < 0:
            raise ContractValidationError("Validation failed: filled_quantity must be >= 0.")
        if not isinstance(self.average_price, (int, float)) or self.average_price < 0:
            raise ContractValidationError("Validation failed: average_price must be >= 0.")

        # Invariant: zero quantity must have zero average price
        if self.filled_quantity == 0 and self.average_price != 0:
            raise ContractValidationError("Validation failed: filled_quantity of 0 must have an average_price of 0.")

        if not isinstance(self.slippage_actual_bps, (int, float)) or not (-10000 <= self.slippage_actual_bps <= 10000):
            raise ContractValidationError("Validation failed: slippage_actual_bps must be within institutional bounds [-10000, 10000].")

        if not isinstance(self.fills, (list, tuple)):
            raise ContractValidationError("Validation failed: fills must be a tuple or list of mappings.")
        object.__setattr__(self, "fills", tuple(freeze_metadata(dict(f)) for f in self.fills))

        for name, dt in [
            ("submitted_at", self.submitted_at),
            ("exchange_acknowledged_at", self.exchange_acknowledged_at),
            ("completed_at", self.completed_at),
            ("execution_timestamp", self.execution_timestamp)
        ]:
            if not isinstance(dt, datetime):
                raise ContractValidationError(f"Validation failed: {name} must be an instance of datetime.")
            if dt.tzinfo is None:
                raise ContractValidationError(f"Validation failed: {name} must contain explicit timezone information.")

        if not isinstance(self.cost_breakdown, Mapping):
            raise ContractValidationError("Validation failed: cost_breakdown must implement Mapping.")
        object.__setattr__(self, "cost_breakdown", freeze_metadata(dict(self.cost_breakdown)))

        if not isinstance(self.broker_response_payload, Mapping):
            raise ContractValidationError("Validation failed: broker_response_payload must implement Mapping.")
        object.__setattr__(self, "broker_response_payload", freeze_metadata(dict(self.broker_response_payload)))

        if not self.payload_hash:
            self.finalize()

    def contract_payload(self) -> Dict[str, Any]:
        return {
            "execution_plan_id": str(self.execution_plan_id),
            "broker_name": self.broker_name,
            "exchange": self.exchange,
            "venue": self.venue,
            "broker_order_id": self.broker_order_id,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "slippage_actual_bps": self.slippage_actual_bps,
            "fills": [dict(f) for f in self.fills],
            "submitted_at": self.submitted_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "exchange_acknowledged_at": self.exchange_acknowledged_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "completed_at": self.completed_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "cost_breakdown": dict(self.cost_breakdown),
            "broker_response_payload": dict(self.broker_response_payload),
            "execution_timestamp": self.execution_timestamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }

    @classmethod
    def create(
        cls,
        execution_plan_id: UUID,
        broker_name: str,
        exchange: str,
        venue: str,
        broker_order_id: str,
        status: ExecutionStatus,
        filled_quantity: float,
        average_price: float,
        slippage_actual_bps: float,
        fills: Tuple[Mapping[str, Any], ...],
        submitted_at: datetime,
        exchange_acknowledged_at: datetime,
        completed_at: datetime,
        cost_breakdown: Mapping[str, Any],
        broker_response_payload: Mapping[str, Any],
        execution_timestamp: datetime,
        producer: str = "broker_adapter",
        producer_version: str = "1.0.0",
        environment: Environment = Environment.PRODUCTION,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "ExecutionResultContract":
        corr_id = correlation_id if correlation_id is not None else uuid4()
        cause_id = causation_id if causation_id is not None else execution_plan_id
        now = datetime.now(timezone.utc)
        resolved_metadata = metadata if metadata is not None else {}

        # Event contracts are born complete in their terminal state with genesis matching terminal trust
        initial_state_history = (
            {
                "state": ContractState.EXECUTED.value,
                "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Immutable execution result record initialized",
            },
        )
        initial_trust_history = (
            {
                "from": TrustLevel.UNVERIFIED.value,
                "to": TrustLevel.EXECUTION_AUTHORIZED.value,
                "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Trade completed under execution authorization",
            },
        )

        instance = cls(
            domain=cls.DOMAIN,
            contract_id=uuid4(),
            contract_type=cls.CONTRACT_TYPE,
            contract_version=1,
            schema_name=cls.SCHEMA_NAME,
            schema_version=cls.SCHEMA_VERSION,
            producer=producer,
            producer_version=producer_version,
            environment=environment,
            created_at=now,
            state=ContractState.EXECUTED,
            trust_level=TrustLevel.EXECUTION_AUTHORIZED,
            state_history=initial_state_history,
            trust_history=initial_trust_history,
            parent_contract_id=execution_plan_id,
            correlation_id=corr_id,
            causation_id=cause_id,
            metadata=resolved_metadata,
            execution_plan_id=execution_plan_id,
            broker_name=broker_name.strip(),
            exchange=exchange.strip(),
            venue=venue.strip(),
            broker_order_id=broker_order_id.strip(),
            status=ExecutionStatus(status),
            filled_quantity=float(filled_quantity),
            average_price=float(average_price),
            slippage_actual_bps=float(slippage_actual_bps),
            fills=fills,
            submitted_at=submitted_at.astimezone(timezone.utc),
            exchange_acknowledged_at=exchange_acknowledged_at.astimezone(timezone.utc),
            completed_at=completed_at.astimezone(timezone.utc),
            cost_breakdown=cost_breakdown,
            broker_response_payload=broker_response_payload,
            execution_timestamp=execution_timestamp.astimezone(timezone.utc),
        )
        instance.finalize()
        return instance

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionResultContract":
        payload = data.get("payload", {})
        return cls(
            domain=data["domain"],
            contract_id=UUID(data["contract_id"]),
            contract_type=data["contract_type"],
            contract_version=data["contract_version"],
            schema_name=data["schema_name"],
            schema_version=data["schema_version"],
            producer=data["producer"],
            producer_version=data["producer_version"],
            environment=Environment(data["environment"]),
            hash_algorithm=data.get("hash_algorithm", "sha256"),
            event_type=data.get("event_type"),
            state=ContractState(data["state"]),
            trust_level=TrustLevel(data["trust_level"]),
            state_history=tuple(data.get("state_history", [])),
            trust_history=tuple(data.get("trust_history", [])),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            parent_contract_id=UUID(data["parent_contract_id"]) if data.get("parent_contract_id") else None,
            correlation_id=UUID(data["correlation_id"]) if data.get("correlation_id") else None,
            causation_id=UUID(data["causation_id"]) if data.get("causation_id") else None,
            metadata=data.get("metadata", {}),
            payload_hash=data.get("payload_hash"),
            execution_plan_id=UUID(payload["execution_plan_id"]),
            broker_name=payload.get("broker_name"),
            exchange=payload.get("exchange"),
            venue=payload.get("venue"),
            broker_order_id=payload.get("broker_order_id"),
            status=ExecutionStatus(payload["status"]),
            filled_quantity=payload.get("filled_quantity"),
            average_price=payload.get("average_price"),
            slippage_actual_bps=payload.get("slippage_actual_bps"),
            fills=tuple(payload.get("fills", [])),
            submitted_at=datetime.fromisoformat(payload["submitted_at"].replace("Z", "+00:00")),
            exchange_acknowledged_at=datetime.fromisoformat(payload["exchange_acknowledged_at"].replace("Z", "+00:00")),
            completed_at=datetime.fromisoformat(payload["completed_at"].replace("Z", "+00:00")),
            cost_breakdown=payload.get("cost_breakdown", {}),
            broker_response_payload=payload.get("broker_response_payload", {}),
            execution_timestamp=datetime.fromisoformat(payload["execution_timestamp"].replace("Z", "+00:00")),
        )
