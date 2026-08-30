"""
Master_Terminal.py
-------------------------------------------------------------------------
Phase 4: Quantitative Consensus Engine (Research Layer)

Purpose:
- Combine RS snapshot + scanner factors + consensus pivots
- Generate institutional ranking
- Persist research_watchlist safely using SQLite UPSERT
- Export Excel research matrix

Database Contract:
research_watchlist
PRIMARY KEY (Ticker, Date)

No append operations.
No duplicate inserts.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

from core.config import DB_PATH, MASTER_OUTPUT_PATH
from core.factor_registry import FACTOR_DEFINITIONS
from core.excel_utils import save_excel_with_retry


MIN_FACTOR_COVERAGE = 0.40


# ---------------------------------------------------------
# DATABASE HELPERS
# ---------------------------------------------------------

def normalize_ticker(x):
    return (
        str(x)
        .replace(".NS", "")
        .upper()
        .strip()
    )


def create_watchlist_table(conn):

    conn.execute("""
    CREATE TABLE IF NOT EXISTS research_watchlist
    (
        Ticker TEXT NOT NULL,
        Composite_Score REAL,
        Confidence_Adjusted_Score REAL,
        Tier TEXT,
        Opportunity TEXT,
        Readiness TEXT,
        Coverage_Pct REAL,
        pivot_price REAL,
        pattern TEXT,
        pattern_confidence REAL,
        Date TEXT NOT NULL,

        PRIMARY KEY (Ticker, Date)
    )
    """)

    conn.commit()



def upsert_watchlist(conn, df):

    cursor = conn.cursor()

    columns = [
        "Ticker",
        "Composite_Score",
        "Confidence_Adjusted_Score",
        "Tier",
        "Opportunity",
        "Readiness",
        "Coverage_Pct",
        "pivot_price",
        "pattern",
        "pattern_confidence",
        "Date"
    ]


    sql = """
    INSERT INTO research_watchlist
    (
        Ticker,
        Composite_Score,
        Confidence_Adjusted_Score,
        Tier,
        Opportunity,
        Readiness,
        Coverage_Pct,
        pivot_price,
        pattern,
        pattern_confidence,
        Date
    )
    VALUES (?,?,?,?,?,?,?,?,?,?,?)

    ON CONFLICT(Ticker,Date)
    DO UPDATE SET

        Composite_Score = excluded.Composite_Score,
        Confidence_Adjusted_Score = excluded.Confidence_Adjusted_Score,
        Tier = excluded.Tier,
        Opportunity = excluded.Opportunity,
        Readiness = excluded.Readiness,
        Coverage_Pct = excluded.Coverage_Pct,
        pivot_price = excluded.pivot_price,
        pattern = excluded.pattern,
        pattern_confidence = excluded.pattern_confidence

    """

    records = df[columns].to_records(index=False)


    for row in records:
        cursor.execute(sql, tuple(row))


    conn.commit()



# ---------------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------------

def run():

    print("=" * 75)
    print("🏛️ MASTER TERMINAL: RESEARCH CONSENSUS ENGINE")
    print("=" * 75)


    if not os.path.exists(DB_PATH):
        print("[-] Database missing")
        return


    conn = sqlite3.connect(DB_PATH)


    try:

        # -------------------------------
        # LOAD INPUT DATA
        # -------------------------------

        rs_df = pd.read_sql(
            """
            SELECT *
            FROM daily_snapshot
            WHERE date =
            (
                SELECT MAX(date)
                FROM daily_snapshot
            )
            """,
            conn
        )


        factors_df = pd.read_sql(
            """
            SELECT *
            FROM scanner_factors
            WHERE date =
            (
                SELECT MAX(date)
                FROM scanner_factors
            )
            """,
            conn
        )


        pivots_df = pd.read_sql(
            """
            SELECT
                ticker,
                pivot_price,
                pattern,
                confidence AS pattern_confidence

            FROM consensus_pivots

            WHERE date =
            (
                SELECT MAX(date)
                FROM consensus_pivots
            )
            """,
            conn
        )


    except Exception as e:

        print(f"[-] Database read error: {e}")
        conn.close()
        return



    if rs_df.empty:

        print("[-] No daily snapshot found")
        conn.close()
        return



    # ---------------------------------------------------------
    # NORMALIZE TICKERS
    # ---------------------------------------------------------

    ticker_col = None

    for c in rs_df.columns:

        if c.lower() in ["ticker","symbol"]:
            ticker_col=c
            break


    if ticker_col is None:

        print("[-] No ticker column found")
        conn.close()
        return



    rs_df.rename(
        columns={ticker_col:"Ticker"},
        inplace=True
    )


    rs_df["Ticker"] = rs_df["Ticker"].apply(normalize_ticker)


    factors_df["Ticker"] = (
        factors_df["ticker"]
        .apply(normalize_ticker)
    )


    pivots_df["Ticker"] = (
        pivots_df["ticker"]
        .apply(normalize_ticker)
    )


    # ---------------------------------------------------------
    # FACTOR MATRIX
    # ---------------------------------------------------------

    if not factors_df.empty:

        factor_matrix = (

            factors_df
            .pivot_table(
                index="Ticker",
                columns="factor_name",
                values="score",
                aggfunc="max"
            )
            .reset_index()

        )


        df = pd.merge(
            rs_df,
            factor_matrix,
            on="Ticker",
            how="left"
        )


    else:

        df = rs_df.copy()



    # ---------------------------------------------------------
    # PIVOT MERGE
    # ---------------------------------------------------------

    if not pivots_df.empty:


        pivots_df = (

            pivots_df
            .drop_duplicates(
                subset=["Ticker"],
                keep="first"
            )

        )


        df = pd.merge(
            df,
            pivots_df,
            on="Ticker",
            how="left"
        )


    else:

        df["pivot_price"]=np.nan
        df["pattern"]="NONE"
        df["pattern_confidence"]=0



    # ---------------------------------------------------------
    # SCORE ENGINE
    # ---------------------------------------------------------

    coverage = pd.Series(
        0.0,
        index=df.index
    )


    total_weight = sum(
        x["weight"]
        for x in FACTOR_DEFINITIONS.values()
        if x["family"]!="confirmation"
    )


    raw_score = pd.Series(
        0.0,
        index=df.index
    )


    for factor,meta in FACTOR_DEFINITIONS.items():

        if meta["family"]=="confirmation":
            continue


        if factor in df.columns:


            values = pd.to_numeric(
                df[factor],
                errors="coerce"
            )


            mask = values.notna()


            coverage += (
                mask.astype(float)
                *
                meta["weight"]
            )


            values = values.fillna(0)


            raw_score += (
                values
                *
                meta["weight"]
            )



    df["_coverage"] = (

        coverage /
        total_weight

    ).clip(0,1)



    df["Composite_Score"] = (

        raw_score /
        total_weight /
        df["_coverage"].replace(0,np.nan)

    ).fillna(0).clip(0,1)



    df["Confidence_Adjusted_Score"] = (

        df["Composite_Score"]
        *
        df["_coverage"]

        +

        df["pattern_confidence"]
        .fillna(0)
        *
        0.1

    )


    # ---------------------------------------------------------
    # FINAL DEDUPLICATION
    # ---------------------------------------------------------

    df = (

        df
        .sort_values(
            "Confidence_Adjusted_Score",
            ascending=False
        )
        .drop_duplicates(
            subset=["Ticker"],
            keep="first"
        )

    )



    # Minimum real relative-strength requirement for Tier-1, checked
    # independently of Composite_Score. rs_percentile is ranked against
    # the WHOLE universe (a much larger, more stable pool than any single
    # small-pool pattern scanner feeding into Composite_Score), so it
    # isn't subject to the same small-candidate-pool inflation that can
    # saturate Composite_Score toward 1.0 for every stock while real
    # history is still accumulating. This doesn't replace Composite_Score
    # - it just stops that inflation alone from promoting a stock to the
    # top tier. Verified against real, known-active breakouts (RS
    # 74.8-97.3) - all correctly stayed Tier-1 at this threshold.
    MIN_RS_FOR_TIER1 = 60.0


    def tier(score,cov,rs_pct=None):

        if cov < MIN_FACTOR_COVERAGE:
            return "INSUFFICIENT DATA"

        rs_ok = rs_pct is None or pd.isna(rs_pct) or rs_pct >= MIN_RS_FOR_TIER1

        if score >= .70 and rs_ok:
            return "TIER-1: Core Institutional Leader"

        elif score >= .70 and not rs_ok:
            return "TIER-2: High Probability Setup"

        elif score >= .50:
            return "TIER-2: High Probability Setup"

        elif score >= .30:
            return "TIER-3: Watchlist"

        return "TIER-4: Speculative"



    df["Tier"] = [

        tier(a,b,c)

        for a,b,c in zip(
            df["Composite_Score"],
            df["_coverage"],
            df["rs_percentile"] if "rs_percentile" in df.columns else [None]*len(df)
        )

    ]



    df["Opportunity"] = np.where(

        df["Composite_Score"]>=0.45,

        "Bullish Accumulation",

        "Normal Monitoring"

    )


    df["Readiness"] = np.where(

        df["Composite_Score"]>=0.60,

        "Immediate Trigger Watch",

        "Developing Structure"

    )


    df["Coverage_Pct"] = (

        df["_coverage"]*100

    ).round(1)



    df["Date"] = datetime.now().strftime(
        "%Y-%m-%d"
    )



    # ---------------------------------------------------------
    # DATABASE WRITE
    # ---------------------------------------------------------

    create_watchlist_table(conn)


    # Safety before UPSERT

    df = df.drop_duplicates(
        subset=["Ticker","Date"],
        keep="first"
    )


    upsert_watchlist(
        conn,
        df
    )



    conn.close()



    # ---------------------------------------------------------
    # EXCEL EXPORT
    # ---------------------------------------------------------

    os.makedirs(
        os.path.dirname(MASTER_OUTPUT_PATH),
        exist_ok=True
    )


    save_excel_with_retry(
        df,
        MASTER_OUTPUT_PATH,
        index=False
    )


    print(
        f"✅ RESEARCH CONSENSUS COMPLETED | {len(df)} targets"
    )



if __name__=="__main__":
    run()