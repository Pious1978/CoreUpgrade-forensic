"""
Research/Factor_Validation.py
-------------------------------------------------------------------------
Deliberately minimal. Two statistics only:

  1. Information Coefficient (IC) -- rank correlation between a
     factor's value at time T and the stock's forward return at T+N.
     This is the single most standard "does this factor predict
     anything" test in quant research. |IC| > ~0.03-0.05 is considered
     a real signal in equities; near zero means no predictive value.

  2. Decile returns -- bucket stocks into 10 groups by factor value,
     show average forward return and win rate per bucket. This is
     where you SEE whether top-decile stocks actually outperform
     bottom-decile stocks, and by how much -- the example from the
     conversation (74% win rate top quartile vs 41% bottom) is exactly
     this test.

Everything else on the original wishlist (SHAP, feature importance,
correlation matrix, walk-forward, Monte Carlo) is deferred on purpose:
those tools answer "how do multiple factors interact" and "is this
robust over different regimes," which only matter once you've
confirmed a SINGLE factor has signal at all. Running them now would
just produce sophisticated-looking output on a question you haven't
answered yet.

Usage: run after backfill_historical_snapshots.py has populated
daily_snapshot with at least a few months of weekly RS history.
"""

import sqlite3
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

DB_PATH = r"C:\Users\GS102\OneDrive\Research\Invest\rs_delivery_history.db"


def load_snapshot_history(conn) -> pd.DataFrame:
    """All weekly snapshots with a non-null factor value, sorted by date."""
    df = pd.read_sql_query("""
        SELECT symbol, date, close, rs_percentile
        FROM daily_snapshot
        WHERE rs_percentile IS NOT NULL
        ORDER BY symbol, date
    """, conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def build_factor_forward_return_table(df: pd.DataFrame, horizon_weeks: int) -> pd.DataFrame:
    """
    For each (symbol, date) row with a factor value, finds that same
    symbol's close `horizon_weeks` snapshots later and computes the
    forward return. Pairs that don't have a future snapshot (i.e. the
    most recent ~horizon_weeks of history) are dropped -- you can't
    validate a forward return you don't have data for yet.
    """
    out_rows = []
    for symbol, g in df.groupby("symbol"):
        g = g.sort_values("date").reset_index(drop=True)
        if len(g) <= horizon_weeks:
            continue
        for i in range(len(g) - horizon_weeks):
            factor_val = g.loc[i, "rs_percentile"]
            close_now = g.loc[i, "close"]
            close_future = g.loc[i + horizon_weeks, "close"]
            if close_now <= 0:
                continue
            fwd_return_pct = (close_future / close_now - 1) * 100
            out_rows.append({
                "symbol": symbol,
                "date": g.loc[i, "date"],
                "factor": factor_val,
                "forward_return_pct": fwd_return_pct,
            })
    return pd.DataFrame(out_rows)


def information_coefficient(pair_df: pd.DataFrame) -> dict:
    """
    Spearman rank correlation between factor value and forward return,
    pooled across all symbol/date pairs. Returns IC, p-value, and N.

    Note: pooling all dates together (rather than computing IC per
    date and averaging) is a simplification appropriate for a first
    pass. It mixes time periods, so a strong IC in one regime and a
    weak one in another will partially cancel -- worth knowing, and
    exactly the kind of question WalkForward_Test.py would answer
    properly later if this first pass looks promising.
    """
    if len(pair_df) < 30:
        return {"ic": None, "p_value": None, "n": len(pair_df),
                "note": "Too few pairs to compute a meaningful IC."}
    ic, p_value = spearmanr(pair_df["factor"], pair_df["forward_return_pct"])
    return {"ic": round(ic, 4), "p_value": round(p_value, 4), "n": len(pair_df)}


def decile_returns(pair_df: pd.DataFrame) -> pd.DataFrame:
    """
    Buckets factor values into 10 groups and reports mean forward
    return + win rate per group. Decile 10 = highest factor value.
    """
    if len(pair_df) < 100:
        print(f"⚠️ Only {len(pair_df)} pairs -- decile buckets will be noisy "
              f"with this little data. Treat results as directional, not exact.")

    df = pair_df.copy()
    try:
        df["decile"] = pd.qcut(df["factor"], 10, labels=False, duplicates="drop") + 1
    except ValueError:
        # too few unique factor values for 10 clean buckets
        df["decile"] = pd.qcut(df["factor"], 5, labels=False, duplicates="drop") + 1

    summary = df.groupby("decile").agg(
        avg_forward_return_pct=("forward_return_pct", "mean"),
        median_forward_return_pct=("forward_return_pct", "median"),
        win_rate_pct=("forward_return_pct", lambda x: (x > 0).mean() * 100),
        n=("forward_return_pct", "count"),
    ).round(2)
    return summary


def run_validation(horizon_weeks_list=(4, 12, 26)):
    conn = sqlite3.connect(DB_PATH)
    raw = load_snapshot_history(conn)
    conn.close()

    if raw.empty:
        print("⚠️ No factor history found. Run backfill_historical_snapshots.py first.")
        return

    print(f"[*] Loaded {len(raw)} historical snapshot rows across "
          f"{raw['symbol'].nunique()} symbols.\n")

    for horizon in horizon_weeks_list:
        print(f"{'='*60}")
        print(f"HORIZON: {horizon} weeks forward")
        print(f"{'='*60}")

        pair_df = build_factor_forward_return_table(raw, horizon)
        if pair_df.empty:
            print("⚠️ Not enough history yet for this horizon -- skipping.\n")
            continue

        ic_result = information_coefficient(pair_df)
        print(f"Information Coefficient: {ic_result}")

        if ic_result["ic"] is not None:
            abs_ic = abs(ic_result["ic"])
            if abs_ic < 0.02:
                verdict = "No real signal -- factor looks close to noise at this horizon."
            elif abs_ic < 0.05:
                verdict = "Weak signal -- worth tracking, not yet worth trading on alone."
            else:
                verdict = "Real signal -- worth pursuing further (walk-forward test next)."
            print(f"  -> {verdict}")

        print("\nDecile returns:")
        print(decile_returns(pair_df).to_string())
        print()


if __name__ == "__main__":
    run_validation()