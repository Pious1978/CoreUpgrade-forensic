from dataclasses import dataclass

EXECUTION_MODEL_METADATA_SCHEMA_VERSION = "1.0"

@dataclass(frozen=True, slots=True)
class ExecutionModelMetadata:
    liquidity_model_version: str
    slippage_model_version: str
    market_impact_model_version: str
    fee_model_version: str
