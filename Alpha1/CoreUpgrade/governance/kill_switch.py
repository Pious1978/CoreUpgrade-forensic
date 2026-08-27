from typing import Dict, Any, Tuple

class KillSwitch:
    """
    System-wide safety override monitoring drawdowns, data feeds, margin breaches, and infrastructure failures.
    """
    
    def __init__(self, max_daily_loss_pct: float = 0.03, max_weekly_loss_pct: float = 0.06):
        self.max_daily_loss = max_daily_loss_pct
        self.max_weekly_loss = max_weekly_loss_pct
        self.triggered = False
        self.reason = ""

    def evaluate_triggers(self, portfolio_state: Dict[str, Any]) -> Tuple[bool, str, str]:
        daily_pnl_pct = portfolio_state.get("daily_pnl_pct", 0.0)
        weekly_pnl_pct = portfolio_state.get("weekly_pnl_pct", 0.0)
        oms_connected = portfolio_state.get("oms_connected", True)
        data_feed_stale = portfolio_state.get("data_feed_stale", False)

        if daily_pnl_pct <= -self.max_daily_loss:
            self.triggered = True
            self.reason = f"Max daily loss breached: {daily_pnl_pct*100:.2f}% <= -{self.max_daily_loss*100}%"
            return True, "LIQUIDATE_AND_HALT", self.reason

        if weekly_pnl_pct <= -self.max_weekly_loss:
            self.triggered = True
            self.reason = f"Max weekly loss breached: {weekly_pnl_pct*100:.2f}% <= -{self.max_weekly_loss*100}%"
            return True, "PAUSE_NEW_ORDERS", self.reason

        if not oms_connected or data_feed_stale:
            self.triggered = True
            self.reason = "Infrastructure failure: OMS disconnected or data feed stale."
            return True, "PAUSE_NEW_ORDERS", self.reason

        return False, "NORMAL", "All systems operational."
