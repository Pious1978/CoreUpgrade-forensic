"""
Research Candidate Contract

Represents the concrete domain fact produced by the Research Validation stage.
Utilizes ClassVar for secure class identity, explicit from_dict() with identity 
spoofing guards, factory validation, and conditional finalization.
"""

from dataclasses import dataclass
from typing import Mapping, Any, Dict, Optional, ClassVar
from datetime import datetime, timezone
from uuid import UUID, uuid4
from contracts.base_contract import BaseContract, Environment, freeze_metadata
from contracts.exceptions import ContractValidationError


@dataclass(frozen=True)
class ResearchCandidateContract(BaseContract):
    CONTRACT_TYPE: ClassVar[str] = "research_candidate"
    SCHEMA_NAME: ClassVar[str] = "research_candidate"
    SCHEMA_VERSION: ClassVar[str] = "1.0"

    ticker: str
    market: str
    discovery_score: float
    evidence: Mapping[str, Any]

    def __post_init__(self):
        super().__post_init__()

        if not isinstance(self.ticker, str) or not self.ticker.strip():
            raise ContractValidationError("Validation failed: ticker symbol is mandatory.")
        if not isinstance(self.market, str) or not self.market.strip():
            raise ContractValidationError("Validation failed: market identifier is mandatory.")
        if not isinstance(self.discovery_score, (int, float)) or not (0.0 <= self.discovery_score <= 1.0):
            raise ContractValidationError("Validation failed: discovery_score must be a float between 0.0 and 1.0.")
        if not isinstance(self.evidence, Mapping):
            raise ContractValidationError("Validation failed: evidence must implement the Mapping interface.")

        frozen_evidence = freeze_metadata(dict(self.evidence))
        object.__setattr__(self, "evidence", frozen_evidence)

        if not self.payload_hash:
            self.finalize()

    def contract_payload(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "market": self.market,
            "discovery_score": self.discovery_score,
            "evidence": dict(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchCandidateContract":
        """
        Reconstructs a ResearchCandidateContract instance from a raw serialized envelope dictionary 
        with rigorous identity spoofing checks.
        """
        if data.get("contract_type") != cls.CONTRACT_TYPE:
            raise ContractValidationError(
                f"Identity verification failed: contract_type mismatch. Expected '{cls.CONTRACT_TYPE}', got '{data.get('contract_type')}'."
            )
        if data.get("schema_version") != cls.SCHEMA_VERSION:
            raise ContractValidationError(
                f"Identity verification failed: unsupported schema_version. Expected '{cls.SCHEMA_VERSION}', got '{data.get('schema_version')}'."
            )

        payload = data.get("payload", {})
        return cls(
            contract_id=UUID(data["contract_id"]),
            contract_type=data["contract_type"],
            contract_version=data["contract_version"],
            schema_name=data["schema_name"],
            schema_version=data["schema_version"],
            producer=data["producer"],
            producer_version=data["producer_version"],
            environment=Environment(data["environment"]),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            parent_contract_id=UUID(data["parent_contract_id"]) if data.get("parent_contract_id") else None,
            correlation_id=UUID(data["correlation_id"]) if data.get("correlation_id") else None,
            causation_id=UUID(data["causation_id"]) if data.get("causation_id") else None,
            metadata=data.get("metadata", {}),
            payload_hash=data.get("payload_hash"),
            ticker=payload.get("ticker"),
            market=payload.get("market"),
            discovery_score=payload.get("discovery_score"),
            evidence=payload.get("evidence", {}),
        )

    @classmethod
    def create(
        cls,
        ticker: str,
        market: str,
        discovery_score: float,
        evidence: Mapping[str, Any],
        producer: str = "research_engine",
        producer_version: str = "1.0.0",
        environment: Environment = Environment.PRODUCTION,
        parent_contract_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "ResearchCandidateContract":
        if not ticker or not isinstance(ticker, str) or not ticker.strip():
            raise ContractValidationError("Validation failed: ticker symbol required.")
        if not market or not isinstance(market, str) or not market.strip():
            raise ContractValidationError("Validation failed: market identifier required.")
        if not isinstance(discovery_score, (int, float)) or not (0.0 <= discovery_score <= 1.0):
            raise ContractValidationError("Validation failed: discovery_score must be between 0.0 and 1.0.")
        if evidence is None or not isinstance(evidence, Mapping):
            raise ContractValidationError("Validation failed: evidence mapping is required.")

        corr_id = correlation_id if correlation_id is not None else uuid4()
        resolved_metadata = metadata if metadata is not None else {}

        return cls(
            contract_id=uuid4(),
            contract_type=cls.CONTRACT_TYPE,
            contract_version=1,
            schema_name=cls.SCHEMA_NAME,
            schema_version=cls.SCHEMA_VERSION,
            producer=producer,
            producer_version=producer_version,
            environment=environment,
            created_at=datetime.now(timezone.utc),
            parent_contract_id=parent_contract_id,
            correlation_id=corr_id,
            causation_id=causation_id,
            metadata=resolved_metadata,
            ticker=ticker.strip(),
            market=market.strip(),
            discovery_score=float(discovery_score),
            evidence=evidence,
        )
