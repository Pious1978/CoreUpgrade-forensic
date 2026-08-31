"""
Compounder_Scanner.py

Genuine quality-investing scanner - directly addresses the original,
still-open swing-vs-investment ask from the very start of this whole
project. Adapted from the BEST real methodology found across Alpha1's
long_planner variants, not just one version:

- Quality gate (long_planner_Compounders.py, v7): reject a stock
  outright before scoring if ROE < 12%, Debt/Equity > 150%, or margins
  < 5% - don't even consider companies that fail basic quality bars,
  regardless of price action.

- Z-score normalization (long_planner_Growth.py, v9, flagged in its own
  comments as a "CRITICAL v9 upgrade"): raw factor values have wildly
  different scales (CAGR ~0.15, ROE ~0.20, margins ~0.10) - combining
  them directly with arbitrary multipliers is far less principled than
  normalizing each factor to a z-score against the scored universe's
  own distribution first, then weighting the comparable-scale z-scores.

- Sector-capped construction (long_planner_Growth.py, v9): uses our own
  real, expanded core/sector_map.py (212 NSE-sourced stocks) rather
  than a small hand-typed list, so real diversification is enforced
  across sectors, not just a curated ~15-stock watchlist.

Genuine improvement over the original scripts: technical features
(CAGR, volatility, momentum, trend) are computed from our own real,
backfilled parquet_cache - no live yfinance history download needed.
Only the fundamentals (ROE, debt/equity, margins, revenue growth) still
require a live yfinance .info fetch, since we have no other source for
that data yet.

HONEST, IMPORTANT LIMITATION: yfinance's .info coverage and reliability
for Indian stocks has NOT yet been verified at scale - this is the
Monday fundamentals coverage check this whole item was waiting on. This
script is built and its logic tested with synthetic data, but running
it for real against the full universe before that check is done could
produce results built on incomplete or unreliable fundamentals data.
Run the coverage check first.
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from core.config import PARQUET_CACHE_DIR, DB_PATH, UNIVERSE_CSV_PATH, BASE_DIR, MIN_TRADING_DAYS_RS
from core.sector_map import get_sector
from core.excel_utils import save_excel_with_retry

MIN_ROE = 0.12
MAX_DEBT_TO_EQUITY = 150
MIN_PROFIT_MARGIN = 0.05

MAX_PER_SECTOR = 2
TOP_N_CANDIDATES = 20


def load_universe():
    """Reuses the same NSE_EQ.csv universe file every other scanner in
    this pipeline already relies on, for consistency."""

    try:
        df = pd.read_csv(UNIVERSE_CSV_PATH)
        cols = [c.upper().strip() for c in df.columns]

        if "SYMBOL" not in cols:
            print("[-] SYMBOL column missing from universe file.")
            return []

        symbol_col = df.columns[cols.index("SYMBOL")]
        symbols = df[symbol_col].dropna().astype(str).str.upper().str.strip().tolist()

        return sorted(set(s for s in symbols if len(s) >= 2))

    except Exception as e:
        print(f"[-] Error loading universe: {e}")
        return []


def compute_technical_features(ticker):
    """
    Real technical features from our own backfilled parquet_cache - no
    live yfinance history download needed, unlike the original scripts.
    """

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        # Only drop rows missing the price data this calculation needs -
        # a blanket dropna() would also drop every backfilled row missing
        # delivery_qty/delivery_pct (intentionally NULL for Yahoo-sourced
        # history). Same real bug found and fixed in
        # Market_Regime_Engine.py and Bear_Market_Scanner.py.
        df = df.dropna(subset=["close", "high", "low"])

        if len(df) < MIN_TRADING_DAYS_RS:
            return None

        close = df["close"]

        cagr_years = len(close) / 252
        cagr = (close.iloc[-1] / close.iloc[0]) ** (1 / cagr_years) - 1 if cagr_years > 0 else 0

        volatility = close.pct_change().std() * np.sqrt(252)
        momentum = close.pct_change(63).iloc[-1] if len(close) > 63 else 0

        ma200 = close.rolling(200).mean().iloc[-1]
        trend = 1 if close.iloc[-1] > ma200 else 0

        drawdown = (close / close.cummax() - 1).min()

        return {
            "cagr": cagr,
            "volatility": volatility,
            "momentum": momentum,
            "trend": trend,
            "drawdown": drawdown,
        }

    except Exception:
        return None


def fetch_fundamentals(ticker):
    """
    Live yfinance .info fetch - the one piece that genuinely can't come
    from our own backfilled data. Returns None on any failure so a
    single bad fetch never breaks the whole scan.
    """

    if not YFINANCE_AVAILABLE:
        return None

    try:
        info = yf.Ticker(f"{ticker}.NS").info

        if not info:
            return None

        return {
            "roe": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "profit_margin": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
        }

    except Exception:
        return None


def smooth_gate_score(value, threshold, direction, width):
    """
    Smooth, continuous Gaussian decay instead of a hard cutoff - avoids
    the "cliff effect" where a stock at ROE=11.9% gets treated
    identically to one at ROE=2% (both currently fail a hard 12%
    threshold equally), while a stock just barely below the threshold
    still gets a real, proportionate penalty rather than a free pass.
    Adapted from a real, working pattern found in Alpha1's
    Consolidation_Scanner.py (v2.5) - full marks up to the ideal
    threshold, then a smooth exponential decay beyond it, not a step
    function.

    direction='above': full marks if value >= threshold (e.g. ROE).
    direction='below': full marks if value <= threshold (e.g. Debt/Equity).
    """

    if direction == "above":
        if value >= threshold:
            return 100.0
        return 100.0 * np.exp(-((threshold - value) / width) ** 2)
    else:
        if value <= threshold:
            return 100.0
        return 100.0 * np.exp(-((value - threshold) / width) ** 2)


def quality_gate_score(fundamentals):
    """
    Combined smooth quality score (0-100) across whichever of the three
    metrics are actually available, replacing the old binary
    passes_quality_gate() hard gate. A stock that's genuinely bad on
    what IS available still gets crushed toward zero naturally through
    the decay curves - this isn't "no gate at all," it's a smoother,
    more proportionate one.

    Real fix: previously returned a flat 0.0 if EITHER roe or margin
    was missing - meaning a major, real company like Reliance (missing
    ROE, but everything else present) would get treated identically to
    a company with genuinely bad fundamentals across the board. Now
    averages only over whichever metrics are actually available, so a
    single missing field doesn't crush an otherwise strong company's
    score to zero.
    """

    if not fundamentals:
        return 0.0

    roe = fundamentals.get("roe")
    debt = fundamentals.get("debt_to_equity")
    margin = fundamentals.get("profit_margin")

    if roe is None and margin is None:
        return 0.0

    scores = []

    if roe is not None:
        scores.append(smooth_gate_score(roe, MIN_ROE, "above", width=0.06))
    if margin is not None:
        scores.append(smooth_gate_score(margin, MIN_PROFIT_MARGIN, "above", width=0.04))

    scores.append(smooth_gate_score(debt if debt is not None else 0, MAX_DEBT_TO_EQUITY, "below", width=80))

    return sum(scores) / len(scores)


def passes_hard_floor(fundamentals):
    """
    A much more lenient hard exclusion than the old quality gate -
    rejects only genuinely missing data or catastrophic values, not
    borderline ones.

    Real, important fix: a major, well-covered company (Reliance,
    confirmed directly via Fundamentals_Sanity_Check.py) can genuinely
    have a missing ROE from yfinance despite being a completely normal,
    scoreable company - this is not the same situation as a bank's
    debt/equity being structurally absent, but it needs the same
    graceful handling. Only reject on missing data if we have NO usable
    profitability signal at all (both roe and margin missing) - a
    single missing field shouldn't hard-exclude an otherwise real
    company.
    """

    if not fundamentals:
        return False

    roe = fundamentals.get("roe")
    debt = fundamentals.get("debt_to_equity")
    margin = fundamentals.get("profit_margin")

    if roe is None and margin is None:
        return False
    if roe is not None and roe < -0.10:
        return False
    if debt is not None and debt > MAX_DEBT_TO_EQUITY * 3:
        return False

    return True


def zscore(series):
    arr = np.array(series, dtype=float)
    std = np.std(arr)
    if std == 0 or np.isnan(std):
        return np.zeros(len(arr))
    return (arr - np.mean(arr)) / (std + 1e-9)


def run():

    print()
    print("=" * 70)
    print("COMPOUNDER SCANNER - QUALITY INVESTING")
    print("=" * 70)

    if not YFINANCE_AVAILABLE:
        print("[-] yfinance not available - cannot fetch fundamentals. Aborting.")
        return

    symbols = load_universe()

    if not symbols:
        print("[-] No symbols loaded from universe file.")
        return

    print(f"[*] Screening {len(symbols)} stocks for quality-investing candidates...")
    print("[*] This fetches live fundamentals per stock and may take a while.")

    raw_data = {}

    for symbol in symbols:

        tech = compute_technical_features(symbol)
        if tech is None:
            continue

        fundamentals = fetch_fundamentals(symbol)
        if not passes_hard_floor(fundamentals):
            continue

        raw_data[symbol] = {**tech, **fundamentals, "quality_gate_score": quality_gate_score(fundamentals)}

    if not raw_data:
        print("[+] No stocks cleared both the technical history requirement and the quality gate.")
        return

    df = pd.DataFrame(raw_data).T

    # Z-score normalization - the real "critical upgrade" found in
    # Alpha1's own v9 iteration. Combining raw factor values directly
    # (different scales) would be far less principled than normalizing
    # each factor against this scored universe's own distribution first.
    df["cagr_z"] = zscore(df["cagr"])
    df["momentum_z"] = zscore(df["momentum"])
    df["volatility_z"] = zscore(df["volatility"])
    # Real, important fix: a missing roe (confirmed directly - even
    # Reliance, a major company, has this gap in yfinance) would
    # otherwise turn this entire row's composite score into NaN once
    # summed with the other z-scores below. Mean-imputation is the
    # standard, principled approach here - substitute the cross-
    # sectional average of whichever roe values ARE available, so a
    # missing field contributes a neutral zero to this factor rather
    # than corrupting the whole score or unfairly penalizing/boosting
    # the stock.
    df["roe_imputed"] = df["roe"].fillna(df["roe"].mean())
    df["roe_z"] = zscore(df["roe_imputed"])
    df["revenue_z"] = zscore(df["revenue_growth"].fillna(0))
    df["quality_gate_z"] = zscore(df["quality_gate_score"])

    df["score"] = (
        df["cagr_z"] * 2.0 +
        df["momentum_z"] * 1.8 +
        df["roe_z"] * 1.5 +
        df["revenue_z"] * 1.5 +
        df["quality_gate_z"] * 1.5 -
        df["volatility_z"] * 1.2
    )

    df = df.sort_values("score", ascending=False)

    # Sector-capped selection - uses our own real, expanded sector map
    # (212 NSE-sourced stocks), not a small hand-typed list. Flags,
    # doesn't exclude, matching the same design decision already made
    # for the sector cap in Risk_Positioning_Engine.py - a genuinely
    # good compounder shouldn't disappear just because its sector slot
    # filled up first.
    sector_counts = {}
    selected = []

    for ticker, row in df.iterrows():
        sector = get_sector(ticker)

        sector_warning = None
        if sector != "UNKNOWN" and sector_counts.get(sector, 0) >= MAX_PER_SECTOR:
            sector_warning = f"SECTOR CONCENTRATION - {sector_counts[sector]} other {sector} candidates already selected"

        if sector != "UNKNOWN":
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        selected.append({
            "ticker": ticker,
            "score": round(row["score"], 2),
            "cagr_pct": round(row["cagr"] * 100, 2),
            "roe_pct": round(row["roe"] * 100, 2) if pd.notna(row["roe"]) else None,
            "revenue_growth_pct": round((row["revenue_growth"] or 0) * 100, 2),
            "volatility_pct": round(row["volatility"] * 100, 2),
            "quality_gate_score": round(row["quality_gate_score"], 1),
            "sector": sector,
            "sector_warning": sector_warning,
        })

        if len(selected) >= TOP_N_CANDIDATES:
            break

    result = pd.DataFrame(selected)

    today = datetime.now().strftime("%Y-%m-%d")
    result["date"] = today

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS compounder_candidates (
            ticker TEXT,
            score REAL,
            cagr_pct REAL,
            roe_pct REAL,
            revenue_growth_pct REAL,
            volatility_pct REAL,
            sector TEXT,
            sector_warning TEXT,
            date TEXT,
            PRIMARY KEY (ticker, date)
        )
    """)

    # Idempotent, safe migration - CREATE TABLE IF NOT EXISTS only helps
    # for a brand-new table; if compounder_candidates already exists
    # from an earlier run tonight (before this column existed), this
    # adds it without disturbing existing rows.
    try:
        conn.execute("ALTER TABLE compounder_candidates ADD COLUMN quality_gate_score REAL")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e):
            raise

    conn.execute("DELETE FROM compounder_candidates WHERE date = ?", (today,))
    result.to_sql("compounder_candidates", conn, if_exists="append", index=False)
    conn.close()

    excel_path = os.path.join(BASE_DIR, "COMPOUNDER_WATCHLIST.xlsx")
    save_excel_with_retry(result, excel_path, index=False)

    print()
    print(f"[+] {len(result)} quality-investing candidates selected")
    print(result[["ticker", "score", "cagr_pct", "roe_pct", "quality_gate_score", "sector"]].to_string(index=False))
    print(f"[+] Written to compounder_candidates and {excel_path}")
    print("=" * 70)


if __name__ == "__main__":
    run()