from dataclasses import dataclass

EXECUTION_MODEL_METADATA_SCHEMA_VERSION = "1.0"

@dataclass(frozen=True, slots=True)
class ExecutionModelMetadata:
    liquidity_model_version: str
    slippage_model_version: str
    market_impact_model_version: str
    fee_model_version: str

    def to_dict(self) -> dict[str, str]:
        """Owns serialization mapping for Event Store schema lineage tracking."""
        return {
            "liquidity_model_version": self.liquidity_model_version,
            "slippage_model_version": self.slippage_model_version,
            "market_impact_model_version": self.market_impact_model_version,
            "fee_model_version": self.fee_model_version,
        }
