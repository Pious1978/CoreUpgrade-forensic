from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional
from uuid import UUID, uuid4

from contracts.base import BaseContract
from contracts.enums import ContractState, Environment, TrustLevel


@dataclass(frozen=True)
class ExecutionPlanContract(BaseContract):
    """Canonical execution-planning contract."""

    DOMAIN = "execution"
    CONTRACT_TYPE = "ExecutionPlanContract"
    SCHEMA_NAME = "execution_plan"
    SCHEMA_VERSION = "1.0"

    instrument: str = ""
    order_type: str = ""
    quantity: float = 0.0
    broker_route: str = ""
    slippage_limit_bps: float = 0.0
    risk_checks_passed: bool = False
    execution_parameters: Mapping[str, Any] = None

    @classmethod
    def create(
        cls,
        instrument: str,
        order_type: str,
        quantity: float,
        broker_route: str,
        slippage_limit_bps: float,
        risk_checks_passed: bool,
        execution_parameters: Mapping[str, Any],
        producer: str = "execution_planner",
        producer_version: str = "1.0.0",
        environment: Environment = Environment.PRODUCTION,
        parent_contract_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "ExecutionPlanContract":
        corr_id = correlation_id if correlation_id is not None else uuid4()
        now = datetime.now(timezone.utc)
        resolved_metadata = metadata if metadata is not None else {}
        resolved_parameters = (
            execution_parameters
            if execution_parameters is not None
            else {}
        )

        initial_state_history = (
            {
                "state": ContractState.CREATED.value,
                "timestamp": now.isoformat(
                    timespec="seconds"
                ).replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Execution plan initialized",
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
            state=ContractState.CREATED,
            trust_level=TrustLevel.UNVERIFIED,
            state_history=initial_state_history,
            trust_history=(),
            parent_contract_id=parent_contract_id,
            correlation_id=corr_id,
            causation_id=causation_id,
            metadata=resolved_metadata,
            instrument=instrument.strip(),
            order_type=order_type.strip(),
            quantity=float(quantity),
            broker_route=broker_route.strip(),
            slippage_limit_bps=float(slippage_limit_bps),
            risk_checks_passed=risk_checks_passed,
            execution_parameters=resolved_parameters,
        )

        instance.finalize()
        return instance