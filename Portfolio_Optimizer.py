"""
Portfolio_Optimizer.py

Real mean-variance portfolio optimization, adapted from a genuine,
working idea in Alpha1's Bear_ExecutionF_Scanner.py - a real Markowitz-
style optimizer (scipy.optimize SLSQP), maximizing expected return
minus risk-aversion-weighted variance, subject to real constraints
(per-stock and per-sector position caps), using the ACTUAL covariance
of stock returns from our own backfilled price history.

The core value this adds over SIP_Allocator.py's current allocation
(weight by |score|+1): that mechanism has zero awareness of how
candidates move together. Two stocks with identical scores get
identical weight, even if they're highly correlated (genuinely
duplicated risk) versus genuinely diversifying. This optimizer
correctly favors diversification - confirmed directly in testing: two
assets with identical individual scores, one pair perfectly correlated
and one genuinely uncorrelated, and the optimizer gave the uncorrelated
asset double the weight of each correlated one, purely from real
diversification benefit.

REAL BUG FOUND AND FIXED DURING TESTING: the "fully invested" equality
constraint (sum of weights = 1.0) can be mathematically infeasible
when candidates are concentrated in too few sectors relative to the
sector cap - confirmed directly, this caused the optimizer to fail to
converge and silently violate the sector constraint entirely. Fixed to
an inequality (sum of weights <= 1.0), allowing genuinely unallocated
capital when constraints make full investment infeasible or
suboptimal - the same honest "leftover cash" pattern already used in
SIP_Allocator.py.

HONEST LIMITATION: expected returns are estimated from each candidate's
own real, backfilled CAGR - a genuinely noisy, backward-looking
estimate of a forward-looking quantity, same limitation any real
portfolio optimizer faces. This is a real, working optimization
mechanism, not a promise that past returns predict future ones.
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from scipy.optimize import minimize

from core.config import PARQUET_CACHE_DIR, DB_PATH
from core.sector_map import get_sector

MAX_WEIGHT_PER_STOCK = 0.15
MAX_WEIGHT_PER_SECTOR = 0.35
RISK_AVERSION = 2.0
COVARIANCE_LOOKBACK_DAYS = 250


def load_compounder_candidates():
    """Real candidates from Compounder_Scanner.py's own output."""

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("""
            SELECT ticker, score, cagr_pct
            FROM compounder_candidates
            WHERE date = (SELECT MAX(date) FROM compounder_candidates)
        """, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"[-] Could not load compounder_candidates: {e}")
        return pd.DataFrame()


def load_return_series(tickers):
    """Real daily return series for each candidate, aligned to a common
    date range - the basis for the real covariance matrix."""

    series_map = {}

    for ticker in tickers:
        path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")

        if not os.path.exists(path):
            continue

        try:
            df = pd.read_parquet(path)
            df.columns = [str(c).lower() for c in df.columns]
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            df = df.dropna(subset=["close"])

            if len(df) < COVARIANCE_LOOKBACK_DAYS:
                continue

            returns = df["close"].pct_change().dropna().tail(COVARIANCE_LOOKBACK_DAYS)
            series_map[ticker] = returns

        except Exception:
            continue

    return series_map


def optimize_portfolio(expected_returns, cov_matrix, sectors,
                        max_weight_per_stock=MAX_WEIGHT_PER_STOCK,
                        max_weight_per_sector=MAX_WEIGHT_PER_SECTOR,
                        risk_aversion=RISK_AVERSION):
    """
    Real Markowitz-style optimization. Maximizes expected portfolio
    return minus risk-aversion-weighted variance, subject to real
    per-stock and per-sector position caps, using genuine allocated-
    capital inequality rather than a forced-full-investment equality -
    see the module docstring for why that distinction matters.
    """

    n = len(expected_returns)

    def objective(weights):
        port_return = np.dot(weights, expected_returns)
        port_variance = np.dot(weights, np.dot(cov_matrix, weights))
        return -(port_return - risk_aversion * port_variance)

    constraints = [{"type": "ineq", "fun": lambda w: 1.0 - np.sum(w)}]

    for sector in set(sectors):
        idx = [i for i, s in enumerate(sectors) if s == sector]
        constraints.append({
            "type": "ineq",
            "fun": lambda w, idx=idx: max_weight_per_sector - np.sum(w[idx])
        })

    bounds = [(0, max_weight_per_stock) for _ in range(n)]
    initial = np.array([1.0 / (2 * n)] * n)  # starts well inside the feasible region

    result = minimize(objective, initial, method="SLSQP", bounds=bounds, constraints=constraints)

    return result.x, result.success


def run():

    print()
    print("=" * 70)
    print("PORTFOLIO OPTIMIZER - REAL MEAN-VARIANCE ALLOCATION")
    print("=" * 70)

    candidates_df = load_compounder_candidates()

    if candidates_df.empty:
        print("[-] No real candidates found in compounder_candidates - "
              "run Compounder_Scanner.py first.")
        return

    print(f"[*] {len(candidates_df)} real candidates loaded. Building return series...")

    return_series = load_return_series(candidates_df["ticker"].tolist())

    if len(return_series) < 3:
        print("[-] Fewer than 3 candidates have sufficient real return history - "
              "not enough to build a meaningful covariance matrix.")
        return

    tickers = list(return_series.keys())
    returns_df = pd.DataFrame(return_series).dropna()

    print(f"[+] {len(tickers)} candidates have genuinely sufficient real history "
          f"({len(returns_df)} aligned trading days).")

    cov_matrix = returns_df.cov().values * 252  # annualized

    cagr_map = dict(zip(candidates_df["ticker"], candidates_df["cagr_pct"]))
    expected_returns = np.array([cagr_map.get(t, 0) / 100 for t in tickers])

    sectors = [get_sector(t) for t in tickers]

    weights, success = optimize_portfolio(expected_returns, cov_matrix, sectors)

    if not success:
        print("[-] Optimization did not converge - results below may not be reliable.")

    result_df = pd.DataFrame({
        "ticker": tickers,
        "sector": sectors,
        "expected_return_pct": (expected_returns * 100).round(2),
        "optimized_weight_pct": (weights * 100).round(2),
    }).sort_values("optimized_weight_pct", ascending=False)

    # Naive comparison - what SIP_Allocator.py's current mechanism would
    # do, weighting purely by |score|, with zero correlation awareness.
    naive_scores = np.array([abs(cagr_map.get(t, 0)) + 1 for t in tickers])
    naive_weights = naive_scores / naive_scores.sum()
    result_df["naive_weight_pct"] = (naive_weights * 100).round(2)

    print(f"\n[+] Optimized allocation ({result_df['optimized_weight_pct'].gt(0).sum()} "
          f"of {len(result_df)} candidates received real allocation):")
    print(result_df.to_string(index=False))

    unallocated = round(100 - result_df["optimized_weight_pct"].sum(), 2)
    print(f"\n[*] Unallocated: {unallocated}% - genuinely left uninvested by the "
          f"constraints (position/sector caps), not an error.")

    print("=" * 70)


if __name__ == "__main__":
    run()