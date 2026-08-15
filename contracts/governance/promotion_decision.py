"""
Promotion Decision Contract

Records institutional audit proof of decision-making during promotion gates 
between downstream stages (e.g., Research Signal -> Portfolio Intent).
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
class PromotionDecisionContract(BaseContract):
    DOMAIN: ClassVar[str] = "governance"
    CONTRACT_TYPE: ClassVar[str] = "promotion_decision"
    SCHEMA_NAME: ClassVar[str] = "promotion_decision"
    SCHEMA_VERSION: ClassVar[str] = "1.0"

    source_contract_id: UUID
    target_contract_id: UUID
    promotion_rule_set: str
    decision: str  # "APPROVED", "REJECTED"
    evaluation_metrics: Mapping[str, Any]

    def __post_init__(self):
        super().__post_init__()

        if not isinstance(self.source_contract_id, UUID):
            raise ContractValidationError("Validation failed: source_contract_id must be a UUID.")
        if not isinstance(self.target_contract_id, UUID):
            raise ContractValidationError("Validation failed: target_contract_id must be a UUID.")
        if not isinstance(self.promotion_rule_set, str) or not self.promotion_rule_set.strip():
            raise ContractValidationError("Validation failed: promotion_rule_set is mandatory.")
        if self.decision not in ("APPROVED", "REJECTED", "EXPIRED"):
            raise ContractValidationError(f"Validation failed: invalid decision status '{self.decision}'.")
        if not isinstance(self.evaluation_metrics, Mapping):
            raise ContractValidationError("Validation failed: evaluation_metrics must implement Mapping.")

        object.__setattr__(self, "evaluation_metrics", freeze_metadata(dict(self.evaluation_metrics)))

        if not self.payload_hash:
            self.finalize()

    def contract_payload(self) -> Dict[str, Any]:
        return {
            "source_contract_id": str(self.source_contract_id),
            "target_contract_id": str(self.target_contract_id),
            "promotion_rule_set": self.promotion_rule_set,
            "decision": self.decision,
            "evaluation_metrics": dict(self.evaluation_metrics),
        }

    @classmethod
    def create(
        cls,
        source_contract_id: UUID,
        target_contract_id: UUID,
        promotion_rule_set: str,
        decision: str,
        evaluation_metrics: Mapping[str, Any],
        producer: str = "governance_engine",
        producer_version: str = "1.0.0",
        environment: Environment = Environment.PRODUCTION,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "PromotionDecisionContract":
        corr_id = correlation_id if correlation_id is not None else uuid4()
        now = datetime.now(timezone.utc)
        resolved_metadata = metadata if metadata is not None else {}

        initial_state_history = (
            {
                "state": ContractState.CREATED.value,
                "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Promotion decision recorded",
            },
        )
        initial_trust_history = (
            {
                "from": TrustLevel.UNVERIFIED.value,
                "to": TrustLevel.GOVERNANCE_CERTIFIED.value,
                "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Governance certification attached to decision",
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
            source_contract_id=source_contract_id,
            target_contract_id=target_contract_id,
            promotion_rule_set=promotion_rule_set.strip(),
            decision=decision.strip().upper(),
            evaluation_metrics=evaluation_metrics,
        )
        instance.finalize()
        return instance

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromotionDecisionContract":
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
            source_contract_id=UUID(payload["source_contract_id"]),
            target_contract_id=UUID(payload["target_contract_id"]),
            promotion_rule_set=payload.get("promotion_rule_set"),
            decision=payload.get("decision"),
            evaluation_metrics=payload.get("evaluation_metrics", {}),
        )
