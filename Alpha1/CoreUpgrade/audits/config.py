from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any


class Severity(str, Enum):
    """Standardized severity levels for audit findings."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class DatabaseThresholds:
    """Threshold configurations for database performance and health checks."""
    max_active_connections: int = 100
    slow_query_threshold_ms: float = 500.0
    max_replication_lag_seconds: int = 30


@dataclass
class RiskThresholds:
    """Threshold configurations for risk metrics and exposure limits."""
    max_portfolio_exposure_pct: float = 15.0
    var_confidence_level: float = 0.95


@dataclass
class LiquidityThresholds:
    """Threshold configurations for liquidity ratios and outflow limits."""
    min_liquidity_coverage_ratio: float = 1.2
    max_cash_outflow_pct: float = 20.0


@dataclass
class ThresholdConfig:
    """Container for all category-specific thresholds."""
    database: DatabaseThresholds = field(default_factory=DatabaseThresholds)
    risk: RiskThresholds = field(default_factory=RiskThresholds)
    liquidity: LiquidityThresholds = field(default_factory=LiquidityThresholds)


@dataclass
class AuditEnableConfig:
    """Feature flags to enable or disable audit modules."""
    database_audit: bool = True
    risk_audit: bool = True
    liquidity_audit: bool = True
    schema_audit: bool = True
    research_audit: bool = True
    market_data_audit: bool = True
    pipeline_flow_audit: bool = True


@dataclass
class SeverityMappingConfig:
    """Maps custom alert levels or error codes to standardized Severities."""
    default_severity: Severity = Severity.MEDIUM
    overrides: Dict[str, Severity] = field(default_factory=dict)

    @staticmethod
    def parse_severity(value: str) -> Severity:
        """Safely parse a string into a Severity enum, defaulting to MEDIUM on typo/error."""
        try:
            return Severity(value.upper())
        except ValueError:
            return Severity.MEDIUM


@dataclass
class AuditWeightConfig:
    """Weights used for compliance score calculation."""
    database: float = 0.20
    risk: float = 0.30
    liquidity: float = 0.20
    schema: float = 0.10
    research: float = 0.10
    pipeline: float = 0.10


@dataclass
class ExecutionConfig:
    """Runtime execution parameters."""
    max_workers: int = 8
    timeout_seconds: int = 300
    retry_attempts: int = 2
    fail_fast: bool = False


@dataclass
class EnvironmentConfig:
    """Environment metadata for enterprise traceability."""
    name: str = "DEV"
    region: str = "DEFAULT"
    owner: str = "AUDIT_ENGINE"


@dataclass
class AuditMetadataConfig:
    """Global framework and retention settings."""
    framework_version: str = "1.0.0"
    retention_days: int = 90
    generate_run_id: bool = True


@dataclass
class AuditConfig:
    """Master configuration class for the entire audit framework."""
    enabled_audits: AuditEnableConfig = field(default_factory=AuditEnableConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    severity_mapping: SeverityMappingConfig = field(default_factory=SeverityMappingConfig)
    weights: AuditWeightConfig = field(default_factory=AuditWeightConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    metadata: AuditMetadataConfig = field(default_factory=AuditMetadataConfig)

    def validate_weights(self):
        """Validates that all compliance scoring weights total exactly 1.0."""
        total = (
            self.weights.database +
            self.weights.risk +
            self.weights.liquidity +
            self.weights.schema +
            self.weights.research +
            self.weights.pipeline
        )
        if round(total, 5) != 1.0:
            raise ValueError(f"Audit weights must equal 1.0. Current total = {total}")

    def validate(self):
        """Validates configuration parameters to reject out-of-bounds values."""
        self.validate_weights()

        if self.thresholds.risk.max_portfolio_exposure_pct > 100:
            raise ValueError("Portfolio exposure cannot exceed 100%")
        
        if not (0 < self.thresholds.risk.var_confidence_level < 1):
            raise ValueError("VaR confidence must be between 0 and 1")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditConfig":
        """Builds an AuditConfig instance from a nested dictionary payload and validates it."""
        env_data = data.get("environment", {})
        enabled_data = data.get("enabled_audits", {})
        thresholds_data = data.get("thresholds", {})
        
        db_data = thresholds_data.get("database", {})
        risk_data = thresholds_data.get("risk", {})
        liq_data = thresholds_data.get("liquidity", {})
        
        severity_data = data.get("severity_mapping", {})
        raw_default_severity = severity_data.get("default_severity", "MEDIUM")
        raw_overrides = severity_data.get("overrides", {})

        weights_data = data.get("weights", {})
        execution_data = data.get("execution", {})
        metadata_data = data.get("metadata", {})

        config = cls(
            environment=EnvironmentConfig(**env_data),
            enabled_audits=AuditEnableConfig(**enabled_data),
            thresholds=ThresholdConfig(
                database=DatabaseThresholds(**db_data),
                risk=RiskThresholds(**risk_data),
                liquidity=LiquidityThresholds(**liq_data)
            ),
            severity_mapping=SeverityMappingConfig(
                default_severity=SeverityMappingConfig.parse_severity(raw_default_severity),
                overrides={k: SeverityMappingConfig.parse_severity(v) for k, v in raw_overrides.items()}
            ),
            weights=AuditWeightConfig(**weights_data),
            execution=ExecutionConfig(**execution_data),
            metadata=AuditMetadataConfig(**metadata_data)
        )
        
        config.validate()
        return config

    @classmethod
    def load(cls, path: str) -> "AuditConfig":
        """Loads and validates configuration directly from a YAML file path."""
        import yaml
        with open(path, "r") as file:
            data = yaml.safe_load(file) or {}
        return cls.from_dict(data)
