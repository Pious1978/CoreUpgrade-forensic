"""
Trade_Candidate_Audit.py
-------------------------------------------------------------------------

Purpose:
--------
Audit the final trade_candidates table before connecting
Live Execution Monitor.

Checks:
-------
1. Candidate count
2. Structural quality
3. Pivot availability
4. Pattern quality
5. Confidence
6. Risk model readiness
7. Execution readiness

No database writes.
"""

import sqlite3
import pandas as pd
import numpy as np

from core.config import DB_PATH


def load_trade_candidates():

    conn = sqlite3.connect(DB_PATH)

    try:
        df = pd.read_sql(
            """
            SELECT *
            FROM trade_candidates
            """,
            conn
        )

    except Exception as e:
        print(f"\n[ERROR] Cannot read trade_candidates")
        print(e)
        conn.close()
        return pd.DataFrame()

    conn.close()

    return df


def safe_count(series):
    return int(series.sum())


def safe_numeric_column(df, col_name):
    """
    Returns col_name as a real numeric Series, defaulting every row to 0
    if the column is genuinely missing entirely - rather than
    df.get(col)'s fragile behavior (returns a bare None when a column
    doesn't exist, which breaks any pd.to_numeric()/.fillna() chain
    built assuming a Series). This audit tool's whole purpose is
    catching data-quality problems, so it should report a missing
    column clearly, not crash ungracefully on one.
    """

    if col_name in df.columns:
        return pd.to_numeric(df[col_name], errors="coerce").fillna(0)

    return pd.Series([0] * len(df), index=df.index)


def audit():

    print("\n")
    print("=" * 75)
    print("🔍 TRADE CANDIDATE EXECUTION AUDIT")
    print("=" * 75)


    df = load_trade_candidates()

    if df.empty:
        print("\n❌ No trade candidates found")
        return


    total = len(df)

    print(f"\nTOTAL TRADE CANDIDATES : {total}")

    print("\nAVAILABLE COLUMNS")
    print("-" * 75)

    print(", ".join(df.columns))


    # -------------------------------
    # Structural Checks
    # -------------------------------

    pivot_ok = safe_numeric_column(df, "pivot") > 0

    pattern_series = df["pattern"] if "pattern" in df.columns else pd.Series([""] * len(df), index=df.index)

    pattern_ok = (
        pattern_series
        .astype(str)
        .str.upper()
        .isin([
            "VCP",
            "CUP_AND_HANDLE",
            "CONSOLIDATION",
            "HIGH_TIGHT_FLAG"
        ])
    )


    confidence_ok = safe_numeric_column(df, "confidence") >= 0.5

    composite_ok = safe_numeric_column(df, "composite_score") >= 0.5


    # -------------------------------
    # Risk Checks
    # -------------------------------

    atr_ok = safe_numeric_column(df, "atr14") > 0

    stop_ok = safe_numeric_column(df, "stop_loss") > 0

    target_ok = safe_numeric_column(df, "target_1") > 0

    risk_ok = safe_numeric_column(df, "risk_per_share") > 0


    # -------------------------------
    # Reporting
    # -------------------------------

    print("\n")
    print("=" * 75)
    print("STRUCTURAL QUALITY")
    print("=" * 75)

    print(
        f"Valid Pivot             : {safe_count(pivot_ok)}"
    )

    print(
        f"Valid Pattern           : {safe_count(pattern_ok)}"
    )

    print(
        f"Valid Confidence        : {safe_count(confidence_ok)}"
    )

    print(
        f"Composite Score > 0.5   : {safe_count(composite_ok)}"
    )


    print("\n")
    print("=" * 75)
    print("RISK ENGINE READINESS")
    print("=" * 75)

    print(
        f"ATR Available           : {safe_count(atr_ok)}"
    )

    print(
        f"Stop Loss Available     : {safe_count(stop_ok)}"
    )

    print(
        f"Target Available        : {safe_count(target_ok)}"
    )

    print(
        f"Risk Calculation Ready  : {safe_count(risk_ok)}"
    )


    # -------------------------------
    # Execution Readiness
    # -------------------------------

    execution_ready = (
        pivot_ok
        &
        pattern_ok
        &
        confidence_ok
        &
        composite_ok
        &
        atr_ok
        &
        stop_ok
        &
        risk_ok
    )


    ready_count = safe_count(execution_ready)


    print("\n")
    print("=" * 75)
    print("EXECUTION PIPELINE STATUS")
    print("=" * 75)

    print(
        f"Execution Ready Candidates : {ready_count}"
    )


    if ready_count == 0:

        print("\n⚠️ NO EXECUTION READY SETUPS")
        print(
            "Reason: Risk layer has not produced complete trade plans."
        )

    else:

        print("\n🔥 TOP EXECUTION READY SETUPS")

        cols = [
            "ticker",
            "pivot",
            "pattern",
            "confidence",
            "composite_score",
            "stop_loss",
            "target_1"
        ]

        available_cols = [
            c for c in cols
            if c in df.columns
        ]


        result = (
            df[execution_ready][available_cols]
            .sort_values(
                by="composite_score",
                ascending=False
            )
            .head(20)
        )

        print()

        print(
            result.to_string(index=False)
        )


    print("\n")
    print("=" * 75)
    print("AUDIT COMPLETED")
    print("=" * 75)



if __name__ == "__main__":
    audit()