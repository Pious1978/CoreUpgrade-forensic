"""
SwingBacktest/Daily_Volume_Ratio.py

#54D - Explicit historical signal approximation for RVOL.

Live RVOL (LivePriceEngine): current intraday volume-so-far divided by
typical volume-so-far at this same time of day - needs minute-level
data we don't have historically.

Historical proxy (this file): today's total daily volume divided by
the mean of the prior N COMPLETED sessions (today itself excluded from
its own baseline, to avoid leaking today's volume into the comparison
it's being measured against).

These are genuinely different signals, not interchangeable - this is
why the field is explicitly named daily_volume_ratio, never rvol. The
live LivePriceEngine is never touched or renamed; this proxy exists
alongside it, not in place of it.

Per the agreed plan: #54E's trade simulator will eventually run two
backtests - one requiring daily_volume_ratio >= 1.5 (mirroring the live
RVOL >= 1.5 threshold) and one without any volume confirmation at all -
to directly measure how much of the strategy's historical performance
depends on volume confirmation, rather than assuming the proxy is
equivalent to the real thing.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def compute_daily_volume_ratio(price_history, lookback=20):
    """
    price_history: a point-in-time-truncated DataFrame (from #54A's
    AsOfView.get_price_history()) with a 'volume' column, indexed by
    date, most recent row last.

    Returns None if there isn't yet enough real history for a
    meaningful baseline - never a fabricated or default value.
    """

    if price_history is None or "volume" not in price_history.columns:
        return None

    if len(price_history) < lookback + 1:
        return None

    today_volume = float(price_history["volume"].iloc[-1])
    prior_volumes = price_history["volume"].iloc[-(lookback + 1):-1]
    prior_avg_volume = float(prior_volumes.mean())

    if prior_avg_volume <= 0:
        return None

    return round(today_volume / prior_avg_volume, 4)


if __name__ == "__main__":

    from Historical_Data_Provider import PointInTimeMarketData

    print()
    print("=" * 70)
    print("DAILY VOLUME RATIO - QUICK SELF-CHECK")
    print("=" * 70)

    data = PointInTimeMarketData()

    if not data.trading_dates:
        print("[-] No trading dates available.")
    else:
        sample_date = data.trading_dates[-1]
        view = data.as_of(sample_date)
        tickers = view.get_available_tickers()[:5]

        print(f"\n[*] Sample daily_volume_ratio as of {sample_date.date()}:")
        for ticker in tickers:
            hist = view.get_price_history(ticker)
            ratio = compute_daily_volume_ratio(hist)
            print(f"    {ticker}: {ratio}")

    print("=" * 70)