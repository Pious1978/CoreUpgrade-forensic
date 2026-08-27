class ExecutionStrategySelector:
    """Selects optimal execution algorithms based on market participation thresholds."""

    @staticmethod
    def select_strategy(participation_rate: float) -> str:
        # participation_rate is in percentage (e.g., 0.5%)
        if participation_rate < 1.0:
            return "LIMIT_ORDER"
        elif 1.0 <= participation_rate <= 5.0:
            return "TWAP"
        else:
            return "VWAP_POV"
