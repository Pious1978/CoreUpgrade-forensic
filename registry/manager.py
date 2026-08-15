import hashlib
from contracts.strategy_promotion import StrategyPromotionContract

class StrategyRegistry:
    """Manages immutable versioning, experiment tracking, and registry storage for validated trading strategies."""

    def __init__(self):
        self.registry = {}
        self.experiment_audit_trail = []

    @staticmethod
    def generate_experiment_id(strategy_id: str, params: dict) -> str:
        param_str = str(sorted(params.items()))
        hash_digest = hashlib.sha256(param_str.encode()).hexdigest()[:12]
        return f"EXP-{strategy_id}-{hash_digest}"

    def register_strategy(self, promotion_contract: StrategyPromotionContract) -> bool:
        strategy_key = f"{promotion_contract.strategy_id}-v{promotion_contract.version}"
        
        if promotion_contract.promotion_status == "PRODUCTION_ELIGIBLE":
            self.registry[strategy_key] = promotion_contract
            self.experiment_audit_trail.append({
                "experiment_id": promotion_contract.experiment_id,
                "strategy_key": strategy_key,
                "status": "REGISTERED",
                "timestamp": promotion_contract.created_at
            })
            return True
        return False

    def get_strategy(self, strategy_id: str, version: str = "1.0") -> StrategyPromotionContract:
        key = f"{strategy_id}-v{version}"
        return self.registry.get(key)
