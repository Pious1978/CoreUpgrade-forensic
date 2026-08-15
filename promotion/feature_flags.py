from typing import Dict, Any

class PromotionFeatureFlagService:
    """Evaluates dynamic promotion feature flags per desk, environment, or tenant."""

    def __init__(self) -> None:
        self._flags: Dict[str, bool] = {}

    def set_flag(self, flag_name: str, enabled: bool) -> None:
        self._flags[flag_name] = enabled

    def is_enabled(self, flag_name: str, context: Any = None) -> bool:
        return self._flags.get(flag_name, False)
