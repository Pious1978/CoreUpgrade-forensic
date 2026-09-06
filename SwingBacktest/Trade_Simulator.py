"""
SwingBacktest/Trade_Simulator.py

#54E - Deterministic trade simulator.

Given one trade setup (entry, stop, target_1, target_2, shares) and the
real, point-in-time daily OHLC history after entry, simulates the
trade day-by-day and determines the actual exit - reusing the exact
real formulas from the forensic mapping (Risk_Positioning_Engine.py's
stop/target logic, Position_Manager.py's trailing stop, Exit_Engine.py's
exit priority), not inventing new ones.

Genuinely conservative, declared, and reported same-bar ambiguity
policy: when a single day's range touches both the stop and a target,
daily OHLC alone can't tell us which happened first. Default is
STOP_FIRST (the conservative assumption), explicitly configurable, and
every ambiguous bar is counted and reported - never silently resolved.

Scoped deliberately narrow: this simulates ONE trade at a time, given
already-known entry parameters. It does not generate candidates itself
(that's #54B's job) or manage portfolio-level capital across many
concurrent trades (that's #54F). Fully testable now with synthetic or
manually-specified trades, independent of #54B's progress.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TRAILING_START_PCT = 10    # matches Position_Manager.py's real, live constant
TRAILING_DISTANCE_PCT = 5  # matches Position_Manager.py's real, live constant


def simulate_trade(price_history_after_entry, entry_price, initial_stop,
                    target_1, target_2, shares,
                    trailing_start_pct=TRAILING_START_PCT,
                    trailing_distance_pct=TRAILING_DISTANCE_PCT,
                    same_bar_policy="STOP_FIRST"):
    """
    price_history_after_entry: a real daily OHLC DataFrame (columns
    open/high/low/close), covering the entry date onward, in
    chronological order. The entry date's own bar is included, matching
    how a real breakout day's own range can also be where the position
    gets managed.

    Returns a dict with the real exit outcome, or an explicit
    "still_open" result if the price history runs out before any exit
    condition is met (a genuine, honest outcome - not an error).
    """

    if price_history_after_entry is None or price_history_after_entry.empty:
        return {"exit_reason": "NO_DATA", "exit_price": None, "exit_date": None}

    current_stop = initial_stop
    t1_hit = False
    ambiguous_bars = 0

    for date, bar in price_history_after_entry.iterrows():

        day_high = float(bar["high"])
        day_low = float(bar["low"])

        stop_touched = day_low <= current_stop
        t1_touched = day_high >= target_1
        t2_touched = day_high >= target_2

        # Same-bar ambiguity: daily OHLC can't tell us which of these
        # happened first within the day. Only genuinely ambiguous when
        # the stop AND at least one target are BOTH touched on this bar.
        if stop_touched and (t1_touched or t2_touched):

            ambiguous_bars += 1

            if same_bar_policy == "STOP_FIRST":
                pnl = (current_stop - entry_price) * shares
                return {
                    "exit_reason": "STOP_LOSS",
                    "exit_price": round(current_stop, 2),
                    "exit_date": date,
                    "pnl": round(pnl, 2),
                    "ambiguous_bars": ambiguous_bars,
                    "same_bar_policy_applied": True,
                }
            elif same_bar_policy == "TARGET_FIRST":
                exit_price = target_2 if t2_touched else target_1
                reason = "TARGET_2" if t2_touched else "TARGET_1"
                pnl = (exit_price - entry_price) * shares
                return {
                    "exit_reason": reason,
                    "exit_price": round(exit_price, 2),
                    "exit_date": date,
                    "pnl": round(pnl, 2),
                    "ambiguous_bars": ambiguous_bars,
                    "same_bar_policy_applied": True,
                }

        # Unambiguous stop hit (no target touched this same bar)
        if stop_touched:
            pnl = (current_stop - entry_price) * shares
            return {
                "exit_reason": "STOP_LOSS",
                "exit_price": round(current_stop, 2),
                "exit_date": date,
                "pnl": round(pnl, 2),
                "ambiguous_bars": ambiguous_bars,
                "same_bar_policy_applied": False,
            }

        # Unambiguous target hit - matches Exit_Engine.py's real, live
        # priority order and behavior exactly: TARGET_2 checked first,
        # but critically, TARGET_1 is a FULL exit too, not merely a
        # tracked milestone. Confirmed directly against the live file -
        # my first version of this simulator incorrectly treated T1 as
        # just a marker (conflating it with Live_Execution_Monitor.py's
        # separate, display-only "sticky t1_hit" tracking), which
        # silently let profitable trades run past their real exit point
        # in the simulation. Caught directly in testing before this
        # reached you.
        if t2_touched:
            pnl = (target_2 - entry_price) * shares
            return {
                "exit_reason": "TARGET_2",
                "exit_price": round(target_2, 2),
                "exit_date": date,
                "pnl": round(pnl, 2),
                "ambiguous_bars": ambiguous_bars,
                "same_bar_policy_applied": False,
            }

        if t1_touched:
            t1_hit = True
            pnl = (target_1 - entry_price) * shares
            return {
                "exit_reason": "TARGET_1",
                "exit_price": round(target_1, 2),
                "exit_date": date,
                "pnl": round(pnl, 2),
                "ambiguous_bars": ambiguous_bars,
                "same_bar_policy_applied": False,
            }

        # Trailing stop - matches Position_Manager.py's real, live logic
        # exactly: once profit reaches trailing_start_pct, the stop
        # trails trailing_distance_pct below the day's close, and only
        # ever moves up, never back down.
        day_close = float(bar["close"])
        profit_pct = ((day_close - entry_price) / entry_price) * 100

        if profit_pct >= trailing_start_pct:
            new_stop = day_close * (1 - trailing_distance_pct / 100)
            current_stop = max(current_stop, new_stop)

    # Ran out of price history before any exit condition was met
    last_close = float(price_history_after_entry["close"].iloc[-1])
    unrealized_pnl = (last_close - entry_price) * shares

    return {
        "exit_reason": "STILL_OPEN",
        "exit_price": None,
        "exit_date": None,
        "unrealized_pnl": round(unrealized_pnl, 2),
        "current_stop": round(current_stop, 2),
        "t1_hit": t1_hit,
        "ambiguous_bars": ambiguous_bars,
    }


if __name__ == "__main__":

    import pandas as pd

    print()
    print("=" * 70)
    print("TRADE SIMULATOR - QUICK SELF-CHECK")
    print("=" * 70)

    # A simple, hand-verifiable synthetic trade: enters at 100, rises
    # cleanly to hit target_1 on day 3.
    dates = pd.date_range("2026-01-01", periods=5, freq="B")
    df = pd.DataFrame({
        "open": [100, 102, 105, 108, 110],
        "high": [101, 104, 111, 109, 112],
        "low": [99, 101, 104, 106, 108],
        "close": [100, 103, 108, 107, 111],
    }, index=dates)

    result = simulate_trade(df, entry_price=100, initial_stop=95, target_1=110, target_2=120, shares=10)
    print(f"\n[*] Simple clean-target-hit trade: {result}")

    print("=" * 70)