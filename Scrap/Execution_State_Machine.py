"""
Execution_Ranking_Engine.py
-------------------------------------------------------------------------
Institutional Candidate Ranking Engine (O'Neil/Minervini Discipline)
"""

import pandas as pd

def rank_execution_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    # Map string confidence to numeric values
    conf_map = {"HIGH": 100.0, "MEDIUM": 70.0, "LOW": 40.0}
    if "confidence" in df.columns and df["confidence"].dtype == object:
        df["conf_numeric"] = df["confidence"].map(conf_map).fillna(70.0)
    else:
        df["conf_numeric"] = df.get("confidence", 70.0)

    # Ensure all scoring columns exist with safe defaults
    for col, default in [
        ("rs_score", 50.0),
        ("composite_score", 50.0),
        ("conf_numeric", 70.0),
        ("pivot_strength", 50.0),
        ("volume_dryup_score", 50.0)
    ]:
        if col not in df.columns:
            df[col] = default

    # O'Neil / Minervini Multi-Factor Execution Scoring Formula
    df["execution_score"] = (
        df["rs_score"] * 0.30 +
        df["composite_score"] * 0.25 +
        df["conf_numeric"] * 0.20 +
        df["pivot_strength"] * 0.15 +
        df["volume_dryup_score"] * 0.10
    )

    df = df.sort_values("execution_score", ascending=False)
    return df
