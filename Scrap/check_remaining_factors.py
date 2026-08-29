import sqlite3
conn = sqlite3.connect("rs_delivery_history.db")

known_active = ["HEG", "GLENMARK", "CARRARO", "NAZARA", "UNIPARTS", "GHCLTEXTIL"]
factors_to_check = ["accumulation_ratio", "pivot_extension", "cup_handle_quality", "hybrid_alpha_score", "earnings_gap_strength", "intraday_rvol", "weekly_rvol"]

for factor in factors_to_check:
    print(f"=== {factor} ===")

    cur = conn.execute("""
        SELECT COUNT(DISTINCT score), COUNT(*) FROM scanner_factors
        WHERE factor_name = ?
        AND date = (SELECT MAX(date) FROM scanner_factors)
    """, (factor,))
    distinct, total = cur.fetchone()
    print(f"  {distinct} distinct values out of {total} total rows")

    for ticker in known_active:
        cur2 = conn.execute("""
            SELECT score FROM scanner_factors
            WHERE ticker = ? AND factor_name = ?
            AND date = (SELECT MAX(date) FROM scanner_factors)
        """, (ticker, factor))
        row = cur2.fetchone()
        print(f"    {ticker}: {row[0] if row else 'NOT FOUND'}")
    print()

conn.close()
