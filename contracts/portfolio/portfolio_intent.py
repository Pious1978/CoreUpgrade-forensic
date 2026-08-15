@classmethod
    def create(
        cls,
        instrument: str,
        target_weight: float,
        capital_limit: float,
        holding_period_days: int,
        risk_budget: float,
        portfolio_constraints: Mapping[str, Any],
        producer: str = "portfolio_engine",
        producer_version: str = "1.0.0",
        environment: Environment = Environment.PRODUCTION,
        parent_contract_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "PortfolioIntentContract":
        corr_id = correlation_id if correlation_id is not None else uuid4()
        now = datetime.now(timezone.utc)
        resolved_metadata = metadata if metadata is not None else {}

        initial_state_history = (
            {
                "state": ContractState.CREATED.value,
                "timestamp": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": producer,
                "reason": "Portfolio allocation intent created",
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
            target_weight=float(target_weight),
            capital_limit=float(capital_limit),
            holding_period_days=int(holding_period_days),
            risk_budget=float(risk_budget),
            portfolio_constraints=portfolio_constraints,
        )
        instance.finalize()
        return instance
