"""
Position_Monitor.py  (Trade Management Engine — Stage 2 of 2)
-------------------------------------------------------------------------
Runs DAILY on your open positions after entry.
Trade_Execution_Engine.py ends at entry. This begins there.

What it checks for each open position every day:
  1. Price vs 21 EMA       → is the breakout still holding?
  2. Price vs 10-week MA   → for extended positions, is trend intact?
  3. Volume on up days     → is institutional participation continuing?
  4. RS trend              → is the stock staying a market leader?
  5. Extension             → is it >20% above entry? (switch trail rules)
  6. Mid-target hit        → trigger partial exit reminder
  7. Measured move hit     → full exit consideration

Output for each position:
  HOLD          → all systems green, nothing to do
  TRAIL STOP ↑  → raise your stop (stock has moved in your favour)
  PARTIAL EXIT  → mid-target hit, sell 1/3 now
  WATCH CLOSE   → one signal weakening, don't add, watch daily
  EXIT          → daily close below 21 EMA / weekly close below 10w MA

Input  : open_positions.csv  (written by Trade_Execution_Engine.py)
Output : POSITION_STATUS.xlsx  +  console alerts
         Updates open_positions.csv with new stop levels + status
"""

import os
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import sqlite3

BASE_DIR        = r"C:\Users\GS102\OneDrive\Research\Invest"
POSITIONS_FILE  = os.path.join(BASE_DIR, "open_positions.csv")
OUTPUT_STATUS   = os.path.join(BASE_DIR, "POSITION_STATUS.xlsx")
DB_PATH         = os.path.join(BASE_DIR, "rs_delivery_history.db")


# ---------------------------------------------------------------
# DATA FETCH
# ---------------------------------------------------------------

def fetch_daily_data(symbol: str) -> pd.DataFrame | None:
    ticker = symbol if symbol.endswith(".NS") else symbol + ".NS"
    try:
        df = yf.download(ticker, period="1y", interval="1d",
                         progress=False, threads=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 30:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception:
        return None


def fetch_weekly_data(symbol: str) -> pd.DataFrame | None:
    ticker = symbol if symbol.endswith(".NS") else symbol + ".NS"
    try:
        df = yf.download(ticker, period="1y", interval="1wk",
                         progress=False, threads=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 10:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception:
        return None


# ---------------------------------------------------------------
# INDIVIDUAL CHECKS
# ---------------------------------------------------------------

def check_ema21(df: pd.DataFrame, entry: float) -> dict:
    """
    Signal = daily CLOSE vs 21 EMA.
    Only trigger exit after stock has had at least 5 days above entry
    (prevents exiting on the entry day's noise).
    """
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    ema21 = close.ewm(span=21, adjust=False).mean()
    current     = float(close.iloc[-1])
    ema21_now   = float(ema21.iloc[-1])
    above       = current > ema21_now
    distance    = round(((current - ema21_now) / ema21_now) * 100, 2)

    return {
        "ema21":         round(ema21_now, 2),
        "above_ema21":   above,
        "distance_pct":  distance,
        "signal":        "OK" if above else "⚠️ BELOW 21 EMA — consider exit on CLOSE confirmation",
    }


def check_10week_ma(weekly_df: pd.DataFrame) -> dict:
    """
    10-week MA is the institutional holding line for longer plays.
    Exit trigger: WEEKLY close below 10-week MA (not intraday).
    """
    close = weekly_df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    ma10w  = close.rolling(10).mean()
    current_weekly_close = float(close.iloc[-1])
    ma10w_now            = float(ma10w.iloc[-1])
    above                = current_weekly_close > ma10w_now

    return {
        "ma10w":             round(ma10w_now, 2),
        "current_wk_close":  round(current_weekly_close, 2),
        "above_10wMA":       above,
        "signal": "OK" if above else "🚨 WEEKLY CLOSE BELOW 10-WEEK MA — EXIT signal",
    }


def check_volume_persistence(df: pd.DataFrame) -> dict:
    """
    Checks last 10 sessions: are up-days seeing higher volume than down-days?
    If volume is drying up on up-days and expanding on down-days,
    that's a distribution warning even if price hasn't broken down yet.
    """
    recent = df.tail(10).copy()
    close  = recent["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    vol    = recent["Volume"]
    if isinstance(vol, pd.DataFrame):
        vol = vol.iloc[:, 0]

    price_chg = close.diff()
    up_vol    = vol[price_chg > 0].mean()
    down_vol  = vol[price_chg < 0].mean()
    avg_20    = float(df["Volume"].tail(20).mean() if not isinstance(df["Volume"], pd.DataFrame)
                      else df["Volume"].iloc[:, 0].tail(20).mean())
    recent_avg = float(vol.mean())
    vol_trend  = "DRYING" if recent_avg < avg_20 * 0.8 else "NORMAL"

    if np.isnan(up_vol) or np.isnan(down_vol):
        ratio = 1.0
        signal = "Insufficient data"
    else:
        ratio = round(up_vol / (down_vol + 1), 2)
        if ratio >= 1.3:
            signal = "✅ Up-day volume > Down-day volume — accumulation continuing"
        elif ratio >= 0.8:
            signal = "🟡 Volume neutral — monitor closely"
        else:
            signal = "⚠️ Down-day volume > Up-day volume — possible distribution"

    return {
        "up_vol_avg":       round(float(up_vol), 0) if not np.isnan(up_vol) else 0,
        "down_vol_avg":     round(float(down_vol), 0) if not np.isnan(down_vol) else 0,
        "up_down_ratio":    ratio,
        "volume_trend":     vol_trend,
        "signal":           signal,
    }


def check_rs_trend(symbol: str, conn) -> dict:
    """
    Pulls last 4 weekly RS percentile snapshots from daily_snapshot.
    If RS is declining for 3+ consecutive weeks, flag as weakening.
    """
    if conn is None:
        return {"rs_now": None, "rs_trend": "DB unavailable", "signal": "Cannot check RS"}

    sym_clean = symbol.replace(".NS","")
    try:
        df = pd.read_sql_query("""
            SELECT date, rs_percentile FROM daily_snapshot
            WHERE symbol = ? AND rs_percentile IS NOT NULL
            ORDER BY date DESC LIMIT 8
        """, conn, params=(sym_clean,))
    except Exception:
        return {"rs_now": None, "rs_trend": "Query failed", "signal": "Cannot check RS"}

    if df.empty:
        return {"rs_now": None, "rs_trend": "No history",
                "signal": "⚠️ No RS history in DB — run Master_Terminal.py daily"}

    df = df.sort_values("date")
    rs_vals = df["rs_percentile"].tolist()
    rs_now  = round(rs_vals[-1], 1)

    if len(rs_vals) >= 3:
        declining = all(rs_vals[i] > rs_vals[i+1] for i in range(len(rs_vals)-2, len(rs_vals)-1))
        three_wk_delta = round(rs_vals[-1] - rs_vals[max(0, len(rs_vals)-4)], 1)
    else:
        declining = False
        three_wk_delta = 0

    if rs_now >= 70 and three_wk_delta >= 0:
        signal = f"✅ RS {rs_now} — leader holding strength"
    elif rs_now >= 60 and three_wk_delta > -10:
        signal = f"🟡 RS {rs_now} — acceptable, watch for deterioration"
    elif declining or three_wk_delta < -10:
        signal = f"⚠️ RS {rs_now}, declining {three_wk_delta} pts — stock losing leadership"
    else:
        signal = f"⚠️ RS {rs_now} below 60 — reassess position"

    return {
        "rs_now":         rs_now,
        "rs_4wk_change":  three_wk_delta,
        "signal":         signal,
    }


def check_extension(current_price: float, entry: float, measured_move: float) -> dict:
    """
    Extension = % above entry.
    > 20% → switch trailing from 21 EMA to 10-week MA (give more room).
    > 75% of measured move → approaching target, tighten trail.
    """
    extension_pct = round(((current_price - entry) / entry) * 100, 2)
    progress_pct  = round(((current_price - entry) / max(measured_move - entry, 1)) * 100, 1)

    if extension_pct >= 20:
        trail_mode = "10-WEEK MA  (extended — give it room)"
    else:
        trail_mode = "21 EMA DAILY  (early — keep tight)"

    if progress_pct >= 90:
        target_signal = "🎯 Near measured move — consider full exit or very tight trail"
    elif progress_pct >= 50:
        target_signal = "✅ Past mid-target — trail and let run"
    else:
        target_signal = "📈 Still early in the move"

    return {
        "extension_pct":    extension_pct,
        "mm_progress_pct":  progress_pct,
        "trail_mode":       trail_mode,
        "target_signal":    target_signal,
    }


def check_mid_target(current_price: float, mid_target: float,
                     partial_sold: bool) -> dict:
    hit = current_price >= mid_target
    if hit and not partial_sold:
        return {"hit": True, "action": "🔥 SELL 1/3 POSITION NOW — mid-target reached"}
    elif hit and partial_sold:
        return {"hit": True, "action": "✅ Partial already taken — trail remainder"}
    else:
        remaining_pct = round(((mid_target - current_price) / current_price) * 100, 2)
        return {"hit": False, "action": f"Not yet — {remaining_pct}% away from mid-target"}


# ---------------------------------------------------------------
# COMPOSITE VERDICT
# ---------------------------------------------------------------

def composite_verdict(ema_chk, vol_chk, rs_chk, ext_chk, weekly_chk,
                      days_held: int = 0) -> str:
    """
    Single actionable output per position.
    Priority order: exit signals beat trail signals beat hold.

    days_held guard: EMA and MA exit signals are suppressed for the
    first 3 days. A stock bought at the pivot often dips back to the
    21 EMA on day 1 — that is normal base behaviour, not an exit signal.
    The hard ATR stop in the trade plan is the real protection those
    first 3 days, not the EMA trail.
    """
    # Hard exit conditions — only fire after minimum 3 days held
    if days_held >= 3:
        if not weekly_chk["above_10wMA"] and ext_chk["extension_pct"] > 15:
            return "🚨 EXIT — Weekly close below 10-week MA while extended"
        if not ema_chk["above_ema21"] and ext_chk["extension_pct"] < 15:
            return "🚨 EXIT — Daily close below 21 EMA (early in trade — stop out)"
    else:
        # Days 0-2: warn only — use the hard ATR stop, not the EMA trail
        if not ema_chk["above_ema21"]:
            return (f"⚠️ WATCH — Below 21 EMA on day {days_held} "
                    f"(exit guard active for first 3 days — use hard stop from trade plan)")

    # Distribution warning
    if "Down-day volume" in vol_chk["signal"] and "below" in rs_chk.get("signal",""):
        return "⚠️ WATCH CLOSE — Distribution volume + RS weakening. Tighten trail."

    # Partial exit
    # (handled separately by check_mid_target, shown in output)

    # Trail up
    if ext_chk["extension_pct"] >= 10 and ema_chk["above_ema21"]:
        return f"📈 TRAIL STOP — Raise to {ext_chk['trail_mode']}"

    # All green
    if ema_chk["above_ema21"] and "continuing" in vol_chk["signal"]:
        return "✅ HOLD — All systems green"

    return "🟡 MONITOR — Mixed signals, no action yet"


# ---------------------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------------------

def run():
    print("\n📊 POSITION MONITOR  (Trade Management Engine)\n")
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(POSITIONS_FILE):
        print(f"❌ No open positions file found at {POSITIONS_FILE}")
        print("   Run Trade_Execution_Engine.py first to open positions.")
        return

    positions = pd.read_csv(POSITIONS_FILE)
    # Cast text columns to object dtype explicitly.
    # pandas infers empty columns as float64, which throws TypeError
    # when you assign a string into them (pandas 2.x behaviour).
    for col in ["notes", "status"]:
        if col in positions.columns:
            positions[col] = positions[col].astype(object)
        else:
            positions[col] = ""
    open_pos = positions[positions["status"] == "OPEN"].copy()

    if open_pos.empty:
        print("ℹ️  No open positions to monitor.")
        return

    print(f"   Monitoring {len(open_pos)} open positions as of {today_str}\n")

    # DB for RS history
    try:
        conn = sqlite3.connect(DB_PATH)
    except Exception:
        conn = None

    status_rows = []

    for _, pos in open_pos.iterrows():
        symbol       = str(pos["symbol"])
        entry_price  = float(pos["entry_price"])
        stop         = float(pos["stop"])
        units        = int(pos["units"])
        base_low     = float(pos["base_low"])
        measured_move= float(pos["measured_move"])
        mid_target   = float(pos["mid_target"])
        quality      = float(pos["quality"])
        partial_sold = bool(pos.get("partial_sold", False))
        entry_date   = str(pos.get("entry_date",""))

        print(f"{'─'*68}")
        print(f"  {symbol}   Entry: ₹{entry_price}   Units: {units}")
        print(f"{'─'*68}")

        daily_df  = fetch_daily_data(symbol)
        weekly_df = fetch_weekly_data(symbol)

        if daily_df is None:
            print(f"  ❌ Could not fetch data for {symbol} — skipping\n")
            continue

        close = daily_df["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        current_price = float(close.iloc[-1])

        # Days held
        try:
            entry_dt  = datetime.datetime.strptime(entry_date, "%Y-%m-%d")
            days_held = (datetime.datetime.now() - entry_dt).days
        except Exception:
            days_held = 0

        pnl_pct = round(((current_price - entry_price) / entry_price) * 100, 2)
        pnl_rs  = round((current_price - entry_price) * units, 2)

        print(f"  Current Price  : ₹{current_price}   "
              f"P&L: {'+' if pnl_pct>=0 else ''}{pnl_pct}%  "
              f"(₹{'+' if pnl_rs>=0 else ''}{pnl_rs:,.0f})   "
              f"Days held: {days_held}")

        # Run all checks
        ema_chk     = check_ema21(daily_df, entry_price)
        weekly_chk  = check_10week_ma(weekly_df) if weekly_df is not None else {
            "above_10wMA": True, "ma10w": 0, "signal": "Weekly data unavailable"}
        vol_chk     = check_volume_persistence(daily_df)
        rs_chk      = check_rs_trend(symbol, conn)
        ext_chk     = check_extension(current_price, entry_price, measured_move)
        mid_chk     = check_mid_target(current_price, mid_target, partial_sold)

        verdict = composite_verdict(ema_chk, vol_chk, rs_chk, ext_chk, weekly_chk, days_held)

        # Update suggested stop (trail upward only — never lower a stop)
        suggested_stop = max(stop, ema_chk["ema21"])  # ratchet up, never down
        if ext_chk["extension_pct"] >= 20:
            suggested_stop = max(suggested_stop, weekly_chk.get("ma10w", suggested_stop))

        # Console output
        print(f"\n  📐 EXTENSION      : {ext_chk['extension_pct']}% above entry  |  "
              f"MM progress: {ext_chk['mm_progress_pct']}%")
        print(f"  🔁 TRAIL MODE     : {ext_chk['trail_mode']}")
        print(f"  🎯 TARGET STATUS  : {ext_chk['target_signal']}")
        if mid_chk["hit"] or ext_chk["mm_progress_pct"] >= 40:
            print(f"  💰 PARTIAL EXIT   : {mid_chk['action']}")
        print(f"\n  📈 21 EMA         : ₹{ema_chk['ema21']}  ({ema_chk['signal']})")
        print(f"  📅 10-WEEK MA     : ₹{weekly_chk.get('ma10w','-')}  "
              f"({weekly_chk.get('signal','N/A')})")
        print(f"  🔊 VOLUME         : {vol_chk['signal']}")
        print(f"  📊 RS TREND       : {rs_chk['signal']}")
        print(f"\n  🛑 SUGGESTED STOP : ₹{round(suggested_stop,2)}  "
              f"(current: ₹{stop} — {'raise it' if suggested_stop > stop else 'already current'})")
        print(f"\n  ══ VERDICT ══  {verdict}\n")

        status_rows.append({
            "Date":           today_str,
            "Symbol":         symbol,
            "Entry":          entry_price,
            "Current Price":  current_price,
            "P&L %":          pnl_pct,
            "P&L ₹":          pnl_rs,
            "Days Held":      days_held,
            "21 EMA":         ema_chk["ema21"],
            "10w MA":         weekly_chk.get("ma10w",""),
            "Suggested Stop": round(suggested_stop, 2),
            "Extension %":    ext_chk["extension_pct"],
            "MM Progress %":  ext_chk["mm_progress_pct"],
            "Trail Mode":     ext_chk["trail_mode"],
            "Volume Signal":  vol_chk["signal"],
            "RS Signal":      rs_chk["signal"],
            "Mid Target Hit": mid_chk["action"],
            "VERDICT":        verdict,
        })

        # Update stop in positions file if raised
        if suggested_stop > stop:
            positions.loc[positions["symbol"]==symbol, "stop"] = round(suggested_stop, 2)

        # Mark partial as sold if mid-target hit (next run won't re-alert)
        if mid_chk["hit"] and not partial_sold:
            positions.loc[positions["symbol"]==symbol, "partial_sold"] = True

        # Auto-close if exit verdict
        if "EXIT" in verdict:
            positions.loc[positions["symbol"]==symbol, "status"] = "CLOSED"
            positions.loc[positions["symbol"]==symbol, "notes"] = \
                f"Closed {today_str}: {verdict}"

    if conn:
        conn.close()

    # Write updated positions back
    positions.to_csv(POSITIONS_FILE, index=False)

    # Export daily status report
    if status_rows:
        out = pd.DataFrame(status_rows)
        out.to_excel(OUTPUT_STATUS, index=False)
        print(f"\n✅ Status report → {OUTPUT_STATUS}")
        print(f"📦 Position file updated → {POSITIONS_FILE}")

    print(f"\n📊 POSITION MONITOR COMPLETE  ({today_str})\n")
    print("  Run this script once per day after market close.")
    print("  It will tell you exactly what to do — nothing, trail, partial, or exit.\n")


if __name__ == "__main__":
    run()