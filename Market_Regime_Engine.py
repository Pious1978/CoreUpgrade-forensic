import pandas as pd
import numpy as np
import os
import glob
import sqlite3
from datetime import datetime

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

from core.config import PARQUET_CACHE_DIR, DB_PATH, NIFTY_BENCHMARK_SYMBOL


class MarketRegimeEngine:

    def __init__(self):

        self.INDEX_WHITELIST = {
            "^NSEI",
            "NSEI",
            "NIFTY",
            "NIFTY50",
            "BANKNIFTY",
            "NSEBANK",
            "NIFTYMIDCAP"
        }


    def check_is_index(self, ticker_clean):

        return ticker_clean.upper() in self.INDEX_WHITELIST



    def calculate_roc20(self, df):

        if len(df) < 21:
            return 0.0

        previous = float(df["close"].iloc[-21])
        current = float(df["close"].iloc[-1])

        if previous == 0:
            return 0.0

        return ((current / previous)-1)*100



    def calculate_advance_decline(self, returns):

        advances = (returns > 0).sum()
        declines = (returns < 0).sum()

        if declines == 0:
            return 2.0

        return advances / declines



    def evaluate_market_breadth_and_regime(
            self,
            nifty_df,
            breadth_data,
            all_stocks_returns):


        close = float(nifty_df["close"].iloc[-1])


        sma50 = float(
            nifty_df["sma_50"].iloc[-1]
        )

        sma200 = float(
            nifty_df["sma_200"].iloc[-1]
        )


        nifty_above_50 = close > sma50
        nifty_above_200 = close > sma200


        roc20 = self.calculate_roc20(nifty_df)


        b20 = breadth_data.get(
            "breadth_20",0)

        b50 = breadth_data.get(
            "breadth_50",0)

        b200 = breadth_data.get(
            "breadth_200",0)



        ad_ratio = self.calculate_advance_decline(
            all_stocks_returns
        )



        # =========================
        # SCORE ENGINE
        # =========================


        score_b200 = min(
            100,
            (b200/60)*100
        )*0.25


        score_b50 = min(
            100,
            (b50/50)*100
        )*0.20


        score_b20 = min(
            100,
            (b20/50)*100
        )*0.10



        trend_score = 0

        if nifty_above_50:
            trend_score +=50

        if nifty_above_200:
            trend_score +=50


        score_trend = trend_score*0.20



        roc_score = max(
            0,
            min(
                100,
                ((roc20+10)/20)*100
            )
        )


        score_roc = roc_score*0.10



        if ad_ratio >=1.5:

            ad_score=100

        elif ad_ratio<=0.7:

            ad_score=0

        else:

            ad_score = (
                (ad_ratio-0.7)/0.8
            )*100



        score_ad = ad_score*0.15



        composite = round(
            score_b200+
            score_b50+
            score_b20+
            score_trend+
            score_roc+
            score_ad,
            2
        )



        # =========================
        # STATE MACHINE
        # =========================


        if (
            composite>=70
            and b200>=45
            and nifty_above_200
        ):

            regime="CONFIRMED_UPTREND"



        elif (
            nifty_above_50
            and roc20>2
            and (
                b20>50
                or b50>40
            )
        ):

            regime="EARLY_RECOVERY"



        elif (
            nifty_above_200
            and (
                ad_ratio<0.8
                or b200<40
            )
        ):

            regime="DISTRIBUTION"



        elif (
            composite<35
            and not nifty_above_50
            and not nifty_above_200
        ):

            regime="BEAR"



        else:

            regime="CHOPPY_ACCUMULATION"



        # =========================
        # CONFIDENCE
        # =========================


        if composite>=75:

            confidence="HIGH"

        elif composite>=55:

            confidence="MEDIUM"

        else:

            confidence="LOW"



        exposure={

            "CONFIRMED_UPTREND":1.00,

            "EARLY_RECOVERY":0.50,

            "CHOPPY_ACCUMULATION":0.60,

            "DISTRIBUTION":0.25,

            "BEAR":0.25

        }.get(
            regime,
            0.25
        )



        return {


            "regime":regime,

            "confidence":confidence,

            "composite_score":composite,

            "breadth_20":round(b20,2),

            "breadth_50":round(b50,2),

            "breadth_200":round(b200,2),

            "advance_decline_ratio":
                round(ad_ratio,2),

            "position_multiplier":
                exposure

        }


# ================================================================
# PERSISTENCE LAYER
# ================================================================
#
# The class above was originally a library-only module with no
# __main__ block and no database-write logic anywhere. Nothing in the
# codebase ever instantiated it or persisted its output - confirmed by
# checking the real market_regime table, which had only 2 stale rows
# from over a month ago, using an old, incompatible schema
# (date, breadth_50, breadth_200, regime, total_stocks - missing
# composite_score, confidence, and position_multiplier entirely).
#
# This meant every regime-dependent read in the system (Risk_
# Positioning_Engine.py's exposure multiplier, Live_Execution_Monitor.
# py's regime display) was silently failing its query and falling back
# to a hardcoded "NEUTRAL" default the entire time - not a display bug,
# a genuine, months-old gap in the pipeline.


def compute_breadth_and_returns(cache_dir, benchmark_symbol):
    """
    Computes real market breadth (% of the universe trading above their
    own 20/50/200-day moving average) and each stock's latest 1-day
    return, across every stock in parquet_cache with sufficient history.
    """

    files = glob.glob(os.path.join(cache_dir, "*.parquet"))

    above_20 = above_50 = above_200 = total_valid = 0
    returns = []

    for path in files:

        ticker = os.path.basename(path).replace(".parquet", "")

        if ticker == benchmark_symbol:
            continue

        try:
            df = pd.read_parquet(path)
            df.columns = [str(c).lower() for c in df.columns]
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            # Only drop rows missing the price data this calculation
            # actually needs - a blanket df.dropna() would also drop
            # every backfilled row missing delivery_qty/delivery_pct
            # (intentionally NULL for all Yahoo-backfilled history,
            # since Yahoo has no delivery data), collapsing every
            # stock's usable history back down to the ~38-40 raw
            # bhav-copy days and causing every stock to fail the 200-day
            # threshold below - confirmed as the real cause of a genuine
            # 0% breadth reading across all three timeframes.
            df = df.dropna(subset=["close", "high", "low"])

            if len(df) < 200:
                continue

            close = df["close"]
            current = float(close.iloc[-1])

            sma20 = float(close.rolling(20).mean().iloc[-1])
            sma50 = float(close.rolling(50).mean().iloc[-1])
            sma200 = float(close.rolling(200).mean().iloc[-1])

            if any(np.isnan(x) for x in [sma20, sma50, sma200]):
                continue

            total_valid += 1
            if current > sma20:
                above_20 += 1
            if current > sma50:
                above_50 += 1
            if current > sma200:
                above_200 += 1

            if len(close) >= 2:
                daily_return = (current - float(close.iloc[-2])) / float(close.iloc[-2])
                returns.append(daily_return)

        except Exception:
            continue

    if total_valid == 0:
        return {"breadth_20": 0, "breadth_50": 0, "breadth_200": 0}, pd.Series(dtype=float)

    breadth_data = {
        "breadth_20": round((above_20 / total_valid) * 100, 2),
        "breadth_50": round((above_50 / total_valid) * 100, 2),
        "breadth_200": round((above_200 / total_valid) * 100, 2),
    }

    return breadth_data, pd.Series(returns)


def migrate_market_regime_schema(db_path):
    """
    Idempotent, safe migration - preserves any existing rows, only adds
    columns that are genuinely missing. Handles the real, confirmed case
    of an old table with an incompatible schema sitting in production.
    """

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS market_regime (date TEXT PRIMARY KEY)")

    needed_columns = [
        ("regime", "TEXT"),
        ("confidence", "TEXT"),
        ("composite_score", "REAL"),
        ("breadth_20", "REAL"),
        ("breadth_50", "REAL"),
        ("breadth_200", "REAL"),
        ("advance_decline_ratio", "REAL"),
        ("position_multiplier", "REAL"),
        ("india_vix", "REAL"),
        ("vix_adjusted_multiplier", "REAL"),
        ("is_distribution_day", "INTEGER"),
        ("distribution_day_count_25d", "INTEGER"),
    ]

    for col_name, col_type in needed_columns:
        try:
            cur.execute(f"ALTER TABLE market_regime ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e):
                raise

    conn.commit()
    conn.close()


def fetch_india_vix():
    """
    Live India VIX fetch - genuinely different information from our
    breadth-based regime detection (options-implied fear/uncertainty,
    not price/breadth action). Never allowed to break the proven,
    breadth-based regime calculation if this fails - returns None on
    any failure, and every caller treats None as "no adjustment,"
    not an error.
    """

    if not YFINANCE_AVAILABLE:
        return None

    try:
        vix_data = yf.Ticker("^INDIAVIX").history(period="1d")
        if vix_data.empty:
            return None
        return round(float(vix_data["Close"].iloc[-1]), 2)
    except Exception:
        return None


def calculate_vix_adjustment(vix_value):
    """
    Real, documented thresholds based on typical India VIX ranges:
    <20 normal/calm, 20-25 elevated, >=25 high fear. A modest,
    transparent reduction layered on top of the breadth-based exposure -
    not an override of the regime classification itself, since VIX can
    spike ahead of price/breadth fully reflecting real market stress.
    """

    if vix_value is None:
        return 1.0, "VIX unavailable - no adjustment applied"

    if vix_value >= 25:
        return 0.70, f"VIX {vix_value} - high fear, exposure reduced 30%"
    elif vix_value >= 20:
        return 0.85, f"VIX {vix_value} - elevated, exposure reduced 15%"
    else:
        return 1.0, f"VIX {vix_value} - normal/calm, no adjustment"


def check_distribution_day(nifty_df):
    """
    Real distribution-day check - a genuine down day on rising volume,
    the classic Minervini/IBD "institutional selling pressure" signal.
    Uses our own real, backfilled NIFTYBEES history - no live fetch
    needed at all, unlike the VIX cross-check.

    Uses the real, professional 25-trading-day window rather than
    Alpha1's simpler 10-day version - the standard IBD convention is
    "5 or more distribution days within 25 trading days" as a genuine
    warning sign, and a 10-day window is too short to be statistically
    meaningful.
    """

    if len(nifty_df) < 2:
        return False

    close_today = float(nifty_df["close"].iloc[-1])
    close_yesterday = float(nifty_df["close"].iloc[-2])
    volume_today = float(nifty_df["volume"].iloc[-1])
    volume_yesterday = float(nifty_df["volume"].iloc[-2])

    return close_today < close_yesterday and volume_today > volume_yesterday


def get_rolling_distribution_day_count(db_path, window=25):
    """
    Real, rolling count from our own accumulated market_regime history -
    genuinely limited right now since this table only has a handful of
    real dates so far, but grows more statistically meaningful every
    day the pipeline runs, same honest framing as Time-in-State tracking
    built earlier tonight.
    """

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql(f"""
            SELECT is_distribution_day FROM market_regime
            ORDER BY date DESC LIMIT {window}
        """, conn)
        conn.close()

        if df.empty:
            return 0, 0

        real_days = int(df["is_distribution_day"].notna().sum())
        count = int(df["is_distribution_day"].fillna(0).sum())

        return count, real_days

    except Exception:
        return 0, 0


def run():

    print()
    print("=" * 70)
    print("MARKET REGIME ENGINE")
    print("=" * 70)

    nifty_path = os.path.join(PARQUET_CACHE_DIR, f"{NIFTY_BENCHMARK_SYMBOL}.parquet")

    if not os.path.exists(nifty_path):
        print(f"[-] Benchmark file not found: {nifty_path}")
        return

    nifty_df = pd.read_parquet(nifty_path)
    nifty_df.columns = [str(c).lower() for c in nifty_df.columns]
    nifty_df["date"] = pd.to_datetime(nifty_df["date"])
    nifty_df = nifty_df.set_index("date").sort_index()
    nifty_df["sma_50"] = nifty_df["close"].rolling(50).mean()
    nifty_df["sma_200"] = nifty_df["close"].rolling(200).mean()

    if pd.isna(nifty_df["sma_200"].iloc[-1]):
        print("[-] Insufficient benchmark history for a real 200-day SMA yet.")
        return

    print("[*] Computing market breadth across the universe...")
    breadth_data, all_stocks_returns = compute_breadth_and_returns(PARQUET_CACHE_DIR, NIFTY_BENCHMARK_SYMBOL)

    engine = MarketRegimeEngine()
    result = engine.evaluate_market_breadth_and_regime(nifty_df, breadth_data, all_stocks_returns)

    print("[*] Fetching real-time India VIX for a complementary volatility check...")
    india_vix = fetch_india_vix()
    vix_factor, vix_note = calculate_vix_adjustment(india_vix)
    vix_adjusted_multiplier = round(result["position_multiplier"] * vix_factor, 3)

    today = datetime.now().strftime("%Y-%m-%d")

    migrate_market_regime_schema(DB_PATH)

    print("[*] Checking for a real distribution day (down day on rising volume)...")
    is_dist_day = check_distribution_day(nifty_df)
    dist_day_count, real_days_available = get_rolling_distribution_day_count(DB_PATH, window=25)

    # Real, established IBD warning threshold - 5+ distribution days
    # within 25 trading days signals genuine institutional selling
    # pressure. Applied as a further reduction on top of the VIX
    # adjustment, same chained-multiplier pattern.
    if dist_day_count >= 5:
        dist_day_factor = 0.85
        dist_day_note = f"{dist_day_count} distribution days in the last {real_days_available} real trading days - elevated, exposure reduced 15%"
    else:
        dist_day_factor = 1.0
        dist_day_note = f"{dist_day_count} distribution days in the last {real_days_available} real trading days - normal"

    final_multiplier = round(vix_adjusted_multiplier * dist_day_factor, 3)

    # Stored under the existing vix_adjusted_multiplier column name -
    # Risk_Positioning_Engine.py already reads this exact column as
    # "the best final multiplier available," so no changes needed there.
    # The value now reflects VIX AND distribution-day adjustments
    # chained together, not just VIX alone - the column name is now a
    # bit imprecise, but avoids a cascading rename across both files.
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO market_regime
        (date, regime, confidence, composite_score, breadth_20, breadth_50, breadth_200, advance_decline_ratio, position_multiplier, india_vix, vix_adjusted_multiplier, is_distribution_day, distribution_day_count_25d)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        today, result["regime"], result["confidence"], result["composite_score"],
        result["breadth_20"], result["breadth_50"], result["breadth_200"],
        result["advance_decline_ratio"], result["position_multiplier"],
        india_vix, final_multiplier, int(is_dist_day), dist_day_count
    ))
    conn.commit()
    conn.close()

    print(f"[+] Regime: {result['regime']}  (confidence: {result['confidence']}, composite: {result['composite_score']})")
    print(f"[+] Breadth: 20d={result['breadth_20']}%  50d={result['breadth_50']}%  200d={result['breadth_200']}%")
    print(f"[+] Breadth-based exposure multiplier: {result['position_multiplier']}")
    print(f"[+] India VIX: {india_vix if india_vix is not None else 'unavailable'}  -  {vix_note}")
    print(f"[+] Today a distribution day: {is_dist_day}  -  {dist_day_note}")
    print(f"[+] Final exposure multiplier (breadth x VIX x distribution): {final_multiplier}")
    print("=" * 70)


if __name__ == "__main__":
    run()