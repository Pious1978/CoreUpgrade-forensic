from dataclasses import dataclass

@dataclass(frozen=True)
class PromotionConfiguration:
    """Runtime configuration loaded from external sources (YAML, Vault, Consul)."""
    max_retries: int = 3
    lock_lease_seconds: int = 30
    dry_run_default: bool = False
    telemetry_enabled: bool = True
    strict_lineage: bool = True
