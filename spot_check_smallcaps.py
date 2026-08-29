import pandas as pd
import os

SAMPLE = [
    "SOMATEX", "ARENTERP", "XTGLOBAL", "TAINWALCHM", "SECMARK",
    "KEYFINSERV", "ORICONENT", "MODIRUBBER", "TIPSFILMS", "SAKUMA",
    "RAMCOSYS", "PAVNAIND", "PRECAM", "SIKKO", "NIBL",
    "AIRAN", "AMNPLST", "DANGEE", "ATLANTAA", "SILGO",
]

print(f"{'Ticker':<15}{'Overlap Dates':<16}{'Max Diff %':<14}{'Median Diff %':<16}{'Verdict'}")
print("-" * 75)

for ticker in SAMPLE:

    bhav_path = f"parquet_cache/{ticker}.parquet"
    yahoo_path = f"parquet_cache_archive_yahoo/{ticker}.NS.parquet"

    if not os.path.exists(bhav_path):
        print(f"{ticker:<15}{'N/A':<16}{'N/A':<14}{'N/A':<16}NOT IN PARQUET_CACHE")
        continue

    if not os.path.exists(yahoo_path):
        print(f"{ticker:<15}{'N/A':<16}{'N/A':<14}{'N/A':<16}NO YAHOO ARCHIVE")
        continue

    bhav = pd.read_parquet(bhav_path)
    bhav["date"] = pd.to_datetime(bhav["date"])

    yahoo = pd.read_parquet(yahoo_path)
    yahoo = yahoo.reset_index()
    yahoo.columns = [c.lower() for c in yahoo.columns]
    yahoo["date"] = pd.to_datetime(yahoo["date"])

    merged = pd.merge(
        bhav[["date", "close"]].rename(columns={"close": "bhav_close"}),
        yahoo[["date", "close"]].rename(columns={"close": "yahoo_close"}),
        on="date", how="inner"
    )

    if merged.empty:
        print(f"{ticker:<15}{'0':<16}{'N/A':<14}{'N/A':<16}NO OVERLAPPING DATES")
        continue

    merged["pct_diff"] = ((merged["bhav_close"] - merged["yahoo_close"]).abs() / merged["yahoo_close"]) * 100

    max_diff = round(merged["pct_diff"].max(), 3)
    median_diff = round(merged["pct_diff"].median(), 3)

    verdict = "OK - consistent" if max_diff <= 3.0 else "REVIEW - possible split/bonus"

    print(f"{ticker:<15}{len(merged):<16}{max_diff:<14}{median_diff:<16}{verdict}")
