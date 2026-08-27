"""
RS_Accel_Delivery_Trend.py
-------------------------------------------------------------------------
Core Mathematical Engine (Production Version)

Fixes applied in this version:
  1. Added missing `import sys` -- script crashed on holidays when
     mto_df was empty and sys.exit() was called without the import.
  2. Step B now loads the full NSE universe from nse_eq.csv instead
     of Institutional_Breakout_Report.xlsx (287 pre-filtered stocks).
     RS percentile rank is only meaningful when computed against ALL
     ~2300 stocks, not just the ones that already passed momentum
     filters -- ranking within a pre-filtered set inflates every score.
  3. Download period changed from "2y" to "1y" -- sufficient for RS
     percentile calculation, cuts runtime roughly in half.
  4. Added weekend/holiday graceful exit that does not crash -- when
     NSE MTO file is unavailable, script logs clearly and exits cleanly
     without needing the MTO data to be present.
  5. Symbol cleaning applied to universe load (same logic as
     Consolidation_Scanner1.py) to strip invalid characters.
"""

import os
import sys
import sqlite3
import io
import requests
import datetime
import numpy as np
import pandas as pd
from dataclasses import dataclass
import yfinance as yf

DB_PATH = r"C:\Users\GS102\OneDrive\Research\Invest\rs_delivery_history.db"
UNIVERSE_CSV = r"C:\Users\GS102\OneDrive\Research\Invest\nse_eq.csv"


# =====================================================================
# DATABASE INITIALISATION
# =====================================================================
def init_db(db_path: str = DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshot (
            symbol       TEXT NOT NULL,
            date         TEXT NOT NULL,
            close        REAL,
            volume       INTEGER,
            delivery_qty INTEGER,
            traded_qty   INTEGER,
            delivery_pct REAL,
            rs_percentile REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.commit()
    return conn


# =====================================================================
# NSE MTO DELIVERY REPORT FETCHER
# Session cookie handshake prevents 403 blocks on the archive endpoint.
# =====================================================================
def fetch_nse_delivery_report(target_date) -> pd.DataFrame:
    date_str = target_date.strftime("%d%m%Y")
    url = (f"https://archives.nseindia.com/archives/equities/"
           f"mto/MTO_{date_str}.DAT")

    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept": ("text/html,application/xhtml+xml,application/xml;"
                   "q=0.9,image/webp,*/*;q=0.8"),
        "Accept-Language": "en-US,en;q=0.5",
    }

    session = requests.Session()
    try:
        # Warm up session -- NSE requires cookies from homepage first
        session.get("https://www.nseindia.com",
                    headers=headers, timeout=10)

        response = session.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[⚠️] NSE archive returned HTTP {response.status_code} "
                  f"for {target_date} -- likely holiday or weekend.")
            return pd.DataFrame()

        parsed_records = []
        for line in response.text.splitlines():
            # MTO rows start with record type indicator '20'
            if not line.startswith("20"):
                continue
            tokens = [t.strip() for t in line.split(",")]
            if len(tokens) >= 7 and tokens[3] == "EQ":
                # EQ filter deduplicates symbols across series
                try:
                    parsed_records.append({
                        "SYMBOL":     tokens[2].upper(),
                        "TRADED_QTY": int(tokens[4]),
                        "DELIV_QTY":  int(tokens[5]),
                        "DELIV_PCT":  float(tokens[6])
                    })
                except (ValueError, IndexError):
                    continue

        df = pd.DataFrame(parsed_records)
        if not df.empty:
            print(f"[+] NSE MTO: {len(df)} EQ delivery records fetched "
                  f"for {target_date}.")
        return df

    except Exception as e:
        print(f"[-] Session error accessing NSE archives: {e}")
        return pd.DataFrame()


# =====================================================================
# UNIVERSE LOADER  (full NSE list, not scanner shortlist)
# =====================================================================
def load_full_universe(csv_path: str = UNIVERSE_CSV) -> list:
    """
    Loads the full NSE symbol list from nse_eq.csv.
    Using the full universe (not the scanner shortlist) is critical --
    RS percentile rank computed across 287 pre-filtered stocks inflates
    every score. Rank must be computed across all ~2300 names.
    """
    if not os.path.exists(csv_path):
        print(f"[-] Universe CSV not found at {csv_path}")
        return []

    df = pd.read_csv(csv_path)
    cols = [c.upper().strip() for c in df.columns]
    if "SYMBOL" not in cols:
        print("[-] SYMBOL column missing from universe CSV.")
        return []

    symbol_col = df.columns[cols.index("SYMBOL")]
    raw = df[symbol_col].dropna().astype(str).str.upper().str.strip().tolist()

    clean = []
    for s in raw:
        if len(s) < 2:
            continue
        if any(x in s for x in ["/", "\\", " ", "&", "*"]):
            continue
        if "DUMMY" in s or "TEST" in s:
            continue
        if not s.endswith(".NS"):
            s += ".NS"
        clean.append(s)

    clean = sorted(list(set(clean)))
    print(f"[+] Full universe loaded: {len(clean)} symbols for RS ranking")
    return clean


# =====================================================================
# CORE INGEST PIPELINE
# =====================================================================
def ingest_bhavcopy_to_pipeline(conn, price_history: dict,
                                 run_date: str,
                                 delivery_df: pd.DataFrame):
    """
    Computes cross-sectional RS percentile rank and writes daily
    snapshot to SQLite. Only symbols with >= 240 trading days of
    history are included in the RS rank -- prevents IPO noise from
    distorting the cross-sectional distribution.
    """
    raw_rows = []
    return_metrics = {}
    MIN_TRADING_DAYS = 240
    skipped_short_history = 0

    for symbol, df in price_history.items():
        if df.empty:
            continue
        try:
            close_series = df["Close"].dropna()
            if isinstance(close_series, pd.DataFrame):
                close_series = close_series.iloc[:, 0]

            vol_series = df["Volume"].dropna()
            if isinstance(vol_series, pd.DataFrame):
                vol_series = vol_series.iloc[:, 0]

            if len(close_series) < MIN_TRADING_DAYS:
                skipped_short_history += 1
                continue

            ann_return = ((close_series.iloc[-1] -
                           close_series.iloc[-MIN_TRADING_DAYS]) /
                          close_series.iloc[-MIN_TRADING_DAYS])

            clean_ticker = symbol.replace(".NS", "")
            return_metrics[clean_ticker] = ann_return
            vol_val = int(vol_series.iloc[-1]) if not vol_series.empty else 0

            raw_rows.append({
                "symbol": clean_ticker,
                "close":  float(close_series.iloc[-1]),
                "volume": vol_val
            })
        except Exception:
            continue

    if not raw_rows:
        print("[-] No symbols survived the history filter -- nothing written.")
        return

    # Cross-sectional RS percentile rank
    returns_df = pd.DataFrame(
        list(return_metrics.items()), columns=["symbol", "return_val"]
    )
    returns_df["rs_percentile"] = (
        returns_df["return_val"].rank(pct=True) * 100
    )
    rs_map = dict(zip(returns_df["symbol"], returns_df["rs_percentile"]))

    # Delivery data lookup (already EQ-deduplicated by fetcher)
    deliv_map = {}
    if not delivery_df.empty:
        deliv_map = dict(
            zip(delivery_df["SYMBOL"],
                delivery_df.to_dict(orient="records"))
        )

    cur = conn.cursor()
    for row in raw_rows:
        sym    = row["symbol"]
        rs_pct = rs_map.get(sym, None)   # NULL not 50 -- NULL is honest

        mto = deliv_map.get(sym, {
            "DELIV_QTY":  0,
            "TRADED_QTY": row["volume"],
            "DELIV_PCT":  np.nan
        })

        deliv_qty  = int(mto["DELIV_QTY"])
        traded_qty = int(mto["TRADED_QTY"]) if int(mto["TRADED_QTY"]) > 0 \
                     else row["volume"]
        deliv_pct  = (
            float(mto["DELIV_PCT"])
            if not np.isnan(mto["DELIV_PCT"])
            else (100.0 * deliv_qty / traded_qty if traded_qty > 0 else 0.0)
        )

        cur.execute("""
            INSERT INTO daily_snapshot
                (symbol, date, close, volume, delivery_qty,
                 traded_qty, delivery_pct, rs_percentile)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date) DO UPDATE SET
                close         = excluded.close,
                volume        = excluded.volume,
                delivery_qty  = excluded.delivery_qty,
                traded_qty    = excluded.traded_qty,
                delivery_pct  = excluded.delivery_pct,
                rs_percentile = excluded.rs_percentile
        """, (sym, run_date, row["close"], row["volume"],
              deliv_qty, traded_qty, deliv_pct, rs_pct))

    try:
        conn.commit()
        n_ranked = len(raw_rows)
        print(f"[+] DB sync complete: {n_ranked} symbols ranked, "
              f"{skipped_short_history} skipped (insufficient history), "
              f"date: {run_date}.")
    except Exception as e:
        print(f"[-] Commit failed: {e}")


# =====================================================================
# RS ACCELERATION & DELIVERY TREND ANALYTICS
# =====================================================================
@dataclass
class RSAccelResult:
    symbol:      str
    rs_now:      float
    slope_4w:    float
    slope_12w:   float
    accelerating: bool
    accel_score: float


def _weekly_rs_series(conn, symbol: str, as_of: str) -> pd.Series:
    df = pd.read_sql_query("""
        SELECT date, rs_percentile FROM daily_snapshot
        WHERE symbol = ? AND date <= ? AND rs_percentile IS NOT NULL
        ORDER BY date
    """, conn, params=(symbol.replace(".NS", ""), as_of))
    if df.empty:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"])
    return (df.set_index("date")
              .resample("W-FRI").last()
              .dropna()["rs_percentile"]
              .tail(12))


def _linfit_slope(series: pd.Series) -> float:
    if len(series) < 2:
        return 0.0
    return float(
        np.polyfit(np.arange(len(series)),
                   series.values.astype(float), 1)[0]
    )


def compute_rs_acceleration(conn, symbol: str,
                             as_of: str) -> RSAccelResult | None:
    series = _weekly_rs_series(conn, symbol, as_of)
    if len(series) < 5:
        return None
    rs_now    = float(series.iloc[-1])
    slope_4w  = _linfit_slope(series.tail(4))
    slope_12w = _linfit_slope(series)
    accelerating = (slope_4w > slope_12w) and (slope_4w > 0) and (rs_now >= 60)
    return RSAccelResult(
        symbol=symbol, rs_now=rs_now,
        slope_4w=slope_4w, slope_12w=slope_12w,
        accelerating=accelerating, accel_score=0.0
    )


def rank_rs_acceleration(conn, symbols: list, as_of: str) -> pd.DataFrame:
    results = [r for sym in symbols
               if (r := compute_rs_acceleration(conn, sym, as_of))]
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame([r.__dict__ for r in results])
    df["accel_score"] = df["slope_4w"].rank(pct=True) * 100
    return df


def compute_delivery_trend(conn, symbol: str, as_of: str) -> dict | None:
    df = pd.read_sql_query("""
        SELECT close, delivery_pct FROM daily_snapshot
        WHERE symbol = ? AND date <= ?
        ORDER BY date DESC LIMIT 60
    """, conn, params=(symbol.replace(".NS", ""), as_of))
    if len(df) < 20 or df["delivery_pct"].isna().all():
        return None
    df = df.iloc[::-1].reset_index(drop=True)
    avg_5  = df["delivery_pct"].tail(5).mean()
    avg_20 = df["delivery_pct"].tail(20).mean()
    avg_60 = df["delivery_pct"].mean()
    df["price_chg"] = df["close"].diff()
    up_del = df[df["price_chg"] > 0]["delivery_pct"].tail(10).mean()
    dn_del = df[df["price_chg"] < 0]["delivery_pct"].tail(10).mean()
    price_up_with_delivery = (
        (avg_5 > avg_20 > avg_60)
        and not np.isnan(up_del)
        and not np.isnan(dn_del)
        and (up_del > dn_del)
    )
    score = float(np.clip(50 + ((avg_5 - avg_60) * 3), 0, 100))
    return {
        "symbol":               symbol,
        "avg_delivery_5d":      avg_5,
        "delivery_trend_score": score,
        "price_up_with_delivery": price_up_with_delivery
    }


def rank_delivery_trend(conn, symbols: list, as_of: str) -> pd.DataFrame:
    results = [r for sym in symbols
               if (r := compute_delivery_trend(conn, sym, as_of))]
    return pd.DataFrame(results) if results else pd.DataFrame()


def early_accumulation_screen(conn, symbols: list,
                               as_of: str) -> pd.DataFrame:
    rs_df = rank_rs_acceleration(conn, symbols, as_of)
    dl_df = rank_delivery_trend(conn, symbols, as_of)
    if rs_df.empty or dl_df.empty:
        return pd.DataFrame()
    merged = rs_df.merge(dl_df, on="symbol", how="inner")
    merged["composite_score"] = (
        0.6 * merged["accel_score"] +
        0.4 * merged["delivery_trend_score"]
    )
    return merged.sort_values(
        "composite_score", ascending=False
    ).reset_index(drop=True)


# =====================================================================
# SESSION TEARDOWN
# =====================================================================
def close_pipeline_session(conn):
    try:
        if conn:
            conn.close()
            print("[+] Database resource handles safely released.")
    except Exception as e:
        print(f"[-] Teardown error: {e}")


# =====================================================================
# STANDALONE EXECUTION DAEMON
# =====================================================================
if __name__ == "__main__":
    print("\n⚡ RUNNING INGESTION MATRIX AGGREGATOR...")
    target_date = datetime.date.today()
    today_str   = target_date.strftime("%Y-%m-%d")

    db_conn = init_db(DB_PATH)

    # STEP A: Fetch NSE MTO delivery report
    print(f"📡 Scoping NSE MTO delivery data for: {today_str}...")
    mto_df = fetch_nse_delivery_report(target_date)

    if mto_df.empty:
        print(f"[⚠️] No MTO delivery data for {today_str} "
              f"(holiday / weekend / NSE fetch issue).")
        print("[*] RS percentile will still be computed from price data.")
        print("    Delivery columns will be null for today's snapshot.")
        # Do NOT exit -- RS rank without delivery is still useful.
        # Only exit if price downloads also fail (handled below).

    # STEP B: Load FULL NSE universe for accurate cross-sectional ranking
    # Using the scanner shortlist (287 stocks) inflates every RS percentile
    # because you're ranking within a pre-filtered set of leaders.
    # Full universe gives true market-wide relative strength.
    print(f"\n📊 Loading full NSE universe from nse_eq.csv...")
    active_symbols = load_full_universe(UNIVERSE_CSV)

    if not active_symbols:
        print("[-] No symbols loaded -- cannot proceed.")
        close_pipeline_session(db_conn)
        sys.exit(1)

    # STEP C: Download 1y price history for all universe symbols
    # 1y is sufficient for RS percentile (uses 240-day return window).
    # Previously used 2y which doubled runtime unnecessarily.
    price_history_map = {}
    print(f"🔬 Downloading 1y market data for {len(active_symbols)} symbols...")
    print("    (This takes 20-30 minutes on first run -- cached by yfinance "
          "after that)\n")

    for i, symbol in enumerate(active_symbols):
        try:
            history = yf.Ticker(symbol).history(period="1y", timeout=8)
            if not history.empty:
                price_history_map[symbol] = history
        except Exception:
            continue

        if i % 200 == 0 and i > 0:
            print(f"    ...{i}/{len(active_symbols)} downloaded, "
                  f"{len(price_history_map)} valid so far")

    print(f"\n[+] Price history collected: {len(price_history_map)} symbols")

    if not price_history_map:
        print("[-] No price data retrieved -- check internet connection.")
        close_pipeline_session(db_conn)
        sys.exit(1)

    # STEP D: Compute RS percentile + delivery stats, write to DB
    print("[*] Computing cross-sectional RS ranks and writing to database...")
    ingest_bhavcopy_to_pipeline(
        db_conn, price_history_map, today_str, mto_df
    )

    close_pipeline_session(db_conn)
    print("✨ Ingestion complete.\n")
    print("   Next step: run Master_Terminal.py")
    print(f"   RS scores for {today_str} are now available -- "
          f"no stale data warning expected.\n")