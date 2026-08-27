import time
from typing import Dict, Any

class ExecutionRiskEngine:
    """
    TRADE-002: Market anomaly controls (fat finger, velocity).
    TRADE-001: Kill switch integration.
    """
    _kill_switch_active: bool = False
    _volume_1s_window: float = 0.0
    _last_window_time: float = 0.0

    @classmethod
    def activate_kill_switch(cls):
        cls._kill_switch_active = True

    @classmethod
    def evaluate_pre_trade_risk(cls, order: Dict[str, Any], cert: Any) -> None:
        if cls._kill_switch_active:
            raise RuntimeError("RISK REJECT: Global Kill Switch is ACTIVE.")

        notional = float(order.get("price", 0)) * float(order.get("quantity", 0))
        
        # Fat finger check
        if notional > cert.max_order_notional:
            raise RuntimeError(f"RISK REJECT: Notional {notional} exceeds max {cert.max_order_notional}.")

        # Velocity tracking
        current_time = time.time()
        if current_time - cls._last_window_time > 1.0:
            cls._volume_1s_window = 0.0
            cls._last_window_time = current_time
            
        cls._volume_1s_window += notional
        if cls._volume_1s_window > cert.max_velocity_1s:
            raise RuntimeError("RISK REJECT: 1-second velocity limit exceeded.")