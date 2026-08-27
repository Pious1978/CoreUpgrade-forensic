"""
Execution_State_Machine.py
---------------------------------------------------------
O'Neil / Minervini Breakout Lifecycle Engine
"""

def evaluate_trade(
        price: float,
        pivot: float,
        trigger: float,
        rvol: float,
        prev_state: str = "WAITING"
):

    if price <= 0 or pivot <= 0:
        return "WAITING"


    # Failed breakout detection
    if (
        prev_state in [
            "VALID_BREAKOUT",
            "LOW_VOLUME_BREAKOUT",
            "RETEST_SUCCESS"
        ]
        and price < pivot
    ):
        return "FAILED_BREAKOUT"


    # Successful retest
    if (
        prev_state == "VALID_BREAKOUT"
        and pivot <= price < trigger
    ):
        return "RETEST_SUCCESS"


    if price < pivot * 0.97:
        return "BASE_BUILDING"


    elif pivot * 0.97 <= price < pivot:
        return "APPROACHING"


    elif pivot <= price < trigger:
        return "TESTING"


    elif price >= trigger:

        if rvol >= 1.5:
            return "VALID_BREAKOUT"

        else:
            return "LOW_VOLUME_BREAKOUT"


    return "EXTENDED"
