from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionManifest:
    run_id: str
    policy_version: str
    policy_hash: str
    controls_loaded: int
    controls_executed: int
    engine_version: str
    timestamp: str
