"""
Swingbacktest/Historical_Data_Provider.py

#54A - Point-in-time data foundation for the historical backtest.

The single most safety-critical piece of the whole backtest system:
its entire job is guaranteeing that any code asking "what did this
stock's price history look like as of date T" genuinely cannot see
anything beyond T. Every downstream piece (#54B scanner reconstruction,
#54C regime reconstruction) depends on this guarantee holding exactly.

Architecture matches the agreed design: existing live logic (scanners,
Market_Regime_Engine.py) stays unchanged. This provides a data-access
layer that existing code can be pointed at instead of the live,
unrestricted parquet_cache - "same logic, different data provider,"
not a second implementation of anything.

Loads each stock's full real price history once into memory (avoiding
repeated file I/O across what will eventually be hundreds of historical
as-of dates), then serves truncated, point-in-time-correct slices on
demand via PointInTimeMarketData.as_of(date).
"""

import sys
import os

# Add the repo root to the import path - Python only adds this script's
# own directory by default, not the working directory it was launched
# from. Tested directly to confirm this works whether run from the repo
# root or from inside Backtest/ itself.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from core.config import PARQUET_CACHE_DIR


class PointInTimeMarketData:
    """
    Loads every stock's real, full price history once. Provides
    point-in-time-correct, truncated views via as_of(date) - the
    as_of() view genuinely cannot see anything beyond the requested
    date, no matter what's asked of it.
    """

    def __init__(self, parquet_cache_dir=PARQUET_CACHE_DIR):

        self.series_map = {}
        self._load_all_series(parquet_cache_dir)
        self.trading_dates = self._compute_trading_dates()

    def _load_all_series(self, parquet_cache_dir):

        print(f"[*] Loading real price history from {parquet_cache_dir}...")

        for fname in os.listdir(parquet_cache_dir):

            if not fname.endswith(".parquet"):
                continue

            ticker = fname.replace(".parquet", "")
            path = os.path.join(parquet_cache_dir, fname)

            try:
                df = pd.read_parquet(path)
                df.columns = [str(c).lower() for c in df.columns]
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()

                # Only drop rows missing genuinely essential price data -
                # a blanket dropna() would also drop backfilled rows
                # missing delivery_qty/delivery_pct (intentionally NULL
                # for Yahoo-sourced history). Same real bug found and
                # fixed across many scanners tonight.
                required_cols = [c for c in ["close", "high", "low"] if c in df.columns]
                df = df.dropna(subset=required_cols)

                if df.empty:
                    continue

                self.series_map[ticker] = df

            except Exception:
                continue

        print(f"[+] Loaded {len(self.series_map)} stocks' real price history.")

    def _compute_trading_dates(self):
        """
        The real, union set of every trading date that appears in ANY
        stock's history - the backtest iterates over dates that
        genuinely existed, not an arbitrary calendar range that might
        include weekends/holidays with no real data at all.
        """

        all_dates = set()

        for df in self.series_map.values():
            all_dates.update(df.index)

        return sorted(all_dates)

    def as_of(self, date):
        """
        Returns a point-in-time view - every method on the returned
        object is genuinely restricted to data on or before this exact
        date, regardless of what's asked of it.
        """

        return AsOfView(self, pd.Timestamp(date))


class AsOfView:
    """
    A single, point-in-time-correct snapshot. This is the ONLY way
    downstream code (scanners, regime reconstruction) should ever touch
    historical data - never the raw PointInTimeMarketData.series_map
    directly, which would bypass the truncation entirely.
    """

    def __init__(self, market_data, as_of_date):
        self._market_data = market_data
        self.as_of_date = as_of_date

    def get_price_history(self, ticker):
        """
        Real price history for one stock, truncated to as_of_date
        (inclusive). Returns None if the stock has no data at all as of
        this date - correctly handles a stock that hadn't yet started
        trading (recent IPO) as "not eligible yet," not an error.
        """

        full_series = self._market_data.series_map.get(ticker)

        if full_series is None:
            return None

        truncated = full_series[full_series.index <= self.as_of_date]

        return truncated if not truncated.empty else None

    def get_available_tickers(self):
        """
        Every ticker that has at least one row of real data as of this
        date - correctly excludes stocks that hadn't started trading
        yet, without needing any special-casing downstream.
        """

        return [
            ticker for ticker, df in self._market_data.series_map.items()
            if not df[df.index <= self.as_of_date].empty
        ]


if __name__ == "__main__":

    print()
    print("=" * 70)
    print("HISTORICAL DATA PROVIDER - QUICK SELF-CHECK")
    print("=" * 70)

    data = PointInTimeMarketData()

    print(f"\n[+] {len(data.trading_dates)} real trading dates available, "
          f"{data.trading_dates[0].date()} to {data.trading_dates[-1].date()}")

    mid_date = data.trading_dates[len(data.trading_dates) // 2]
    view = data.as_of(mid_date)

    print(f"\n[*] Sample as_of({mid_date.date()}) view:")
    print(f"    {len(view.get_available_tickers())} tickers with data as of this date")

    print("=" * 70)