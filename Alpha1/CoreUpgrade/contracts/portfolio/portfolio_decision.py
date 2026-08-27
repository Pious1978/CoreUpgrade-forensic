"""
Portfolio Decision Contract

Records capital allocation approvals or rejections issued by the Portfolio Manager 
following intent evaluation.
"""

from dataclasses import dataclass
from typing import Mapping, Any, Dict, ClassVar, Optional
from datetime import datetime, timezone
from uuid import UUID
from contracts.base_contract import BaseContract, Environment
from contracts.state import ContractState
from contracts.trust import TrustLevel
from contracts.freezer import freeze_metadata
from contracts.exceptions import ContractValidationError


@dataclass(frozen=True)
class PortfolioDecisionContract(BaseContract):
    DOMAIN: ClassVar[str] = "portfolio"
    CONTRACT_TYPE: ClassVar[str] = "portfolio_decision"
    SCHEMA_NAME: ClassVar[str] = "portfolio_decision"
    SCHEMA_VERSION: ClassVar[str] = "1.0"

    portfolio_intent_id: UUID
    approved_weight: float
    approved_capital: float
    decision: str  # "APPROVED", "REJECTED", "MODIFIED"
    risk_approval_notes: str

    def __post_init__(self):
        super().__post_init__()

        if not isinstance(self.portfolio_intent_id, UUID):
            raise ContractValidationError("Validation failed: portfolio_intent_id must be a UUID.")
        if not isinstance(self.approved_weight, (int, float)) or not (0.0 <= self.approved_weight <= 1.0):
            raise ContractValidationError("Validation failed: approved_weight must be between 0.0 and 1.0.")
        if not isinstance(self.approved_capital, (int, float)) or self.approved_capital < 0:
            raise ContractValidationError("Validation failed: approved_capital must be >= 0.")
        if self.decision not in ("APPROVED", "REJECTED", "MODIFIED"):
            raise ContractValidationError(f"Validation failed: invalid decision status '{self.decision}'.")
        if not isinstance(self.risk_approval_notes, str):
            raise ContractValidationError("Validation failed: risk_approval_notes must be a string.")

        if not self.payload_hash:
            self.finalize()

    def contract_payload(self) -> Dict[str, Any]:
        return {
            "portfolio_intent_id": str(self.portfolio_intent_id),
            "approved_weight": self.approved_weight,
            "approved_capital": self.approved_capital,
            "decision": self.decision,
            "risk_approval_notes": self.risk_approval_notes,
        }

    @classmethod
    def create(
        cls,
        portfolio_intent_id: UUID,
        approved_weight: float,
        approved_capital: float,
        decision: str,
        risk_approval_notes: str,
        producer: str = "portfolio_risk_engine",
        producer_version: str = "1.0.0",
        environment: Environment = Environment.PRODUCTION,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "PortfolioDecisionContract":
        corr_id = correlation_id if correlation_id is not None else uuid4()
        now = datetime.now(timezone.utc)
        resolved_metadata = metadata if metadata is not None else {}

        initial_state_history = (
            {
                "state": ContractState.CREATED.value,
                "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Portfolio allocation decision created",
            },
        )
        initial_trust_history = (
            {
                "from": TrustLevel.UNVERIFIED.value,
                "to": TrustLevel.GOVERNANCE_CERTIFIED.value,
                "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Portfolio governance checks passed",
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
            trust_level=TrustLevel.GOVERNANCE_CERTIFIED,
            state_history=initial_state_history,
            trust_history=initial_trust_history,
            correlation_id=corr_id,
            causation_id=causation_id,
            metadata=resolved_metadata,
            portfolio_intent_id=portfolio_intent_id,
            approved_weight=float(approved_weight),
            approved_capital=float(approved_capital),
            decision=decision.strip().upper(),
            risk_approval_notes=risk_approval_notes.strip(),
        )
        instance.finalize()
        return instance

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioDecisionContract":
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
            portfolio_intent_id=UUID(payload["portfolio_intent_id"]),
            approved_weight=payload.get("approved_weight"),
            approved_capital=payload.get("approved_capital"),
            decision=payload.get("decision"),
            risk_approval_notes=payload.get("risk_approval_notes", ""),
        )
