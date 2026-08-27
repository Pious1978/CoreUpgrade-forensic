@classmethod
    def create(
        cls,
        instrument: str,
        research_id: str,
        signal_type: str,
        discovery_score: float,
        quality_score: float,
        risk_flags: Tuple[str, ...],
        evidence_refs: Mapping[str, Any],
        research_timestamp: datetime,
        producer: str = "research_engine",
        producer_version: str = "1.0.0",
        environment: Environment = Environment.PRODUCTION,
        parent_contract_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "ResearchSignalContract":
        corr_id = correlation_id if correlation_id is not None else uuid4()
        now = datetime.now(timezone.utc)
        resolved_metadata = metadata if metadata is not None else {}

        initial_state_history = (
            {
                "state": ContractState.CREATED.value,
                "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Signal discovery initialized",
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
            research_id=research_id.strip(),
            signal_type=signal_type.strip(),
            discovery_score=float(discovery_score),
            quality_score=float(quality_score),
            risk_flags=risk_flags,
            evidence_refs=evidence_refs,
            research_timestamp=research_timestamp,
        )
        instance.finalize()
        return instance
