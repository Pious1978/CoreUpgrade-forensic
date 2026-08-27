"""
Trade_Execution_Engine.py  (Entry Engine — Stage 1 of 2)
-------------------------------------------------------------------------
Job: Generate a complete entry trade plan for each actionable setup.
     Then write the position to open_positions.csv so Position_Monitor.py
     can take over post-entry management.

What changed from previous version
  - Targets: VCP base height projection replaces fixed R-multiples.
             Base height = Pivot − Base_Low (lowest close of the base).
             Measured Move Target = Pivot + Base_Height.
             21 EMA and 10-week MA become the trailing stop mechanism
             once price is running — NOT a fixed T2/T3 price level.
  - EDP: shown pre-entry only. Removed from post-entry output because
         once you're in, it's irrelevant — Position_Monitor handles
         time-based management.
  - Volume: 3-zone decision (>1.8× buy, 1.5-1.8× half, <1.5× skip).
  - Separation: this file ends at entry. Position_Monitor.py begins there.
"""

import os
import re
import json
import sqlite3
import datetime
import numpy as np
import pandas as pd
import yfinance as yf

BASE_DIR   = r"C:\Users\GS102\OneDrive\Research\Invest"
INPUT_FILE = os.path.join(BASE_DIR, "COMPOSITE_ALPHA_OUTPUT.xlsx")
OUTPUT_PLAN  = os.path.join(BASE_DIR, "TRADE_EXECUTION_PLAN.xlsx")
POSITIONS_FILE = os.path.join(BASE_DIR, "open_positions.csv")
DB_PATH    = os.path.join(BASE_DIR, "rs_delivery_history.db")

RISK_PCT   = 0.005   # 0.5% of capital per trade — conservative, fixed


# ---------------------------------------------------------------
# PARSING HELPERS
# ---------------------------------------------------------------

def parse_score(s):
    try:    return float(str(s).split("/")[0].strip())
    except: return 0.0

def parse_pct(s):
    try:    return float(str(s).replace("%","").strip())
    except: return 0.0

def parse_pivot(trigger):
    m = re.search(r"₹([\d,.]+)", str(trigger))
    return float(m.group(1).replace(",","")) if m else 0.0

def parse_edp_days(edp):
    nums = re.findall(r"\d+", str(edp))
    return int(nums[0]) if nums else 5

def quality_composite(opp, readiness):
    return round(opp * 0.6 + readiness * 0.4, 2)


# ---------------------------------------------------------------
# BASE GEOMETRY — the heart of VCP target calculation
# ---------------------------------------------------------------

def fetch_base_geometry(symbol: str, pivot: float) -> dict:
    """
    Downloads daily data and finds the base structure:
      Base_Low  = lowest close in the 60-day consolidation window
                  (the trough from which the base formed)
      Base_High = pivot (already known)
      Base_Height = Base_High − Base_Low
      Measured_Move = Pivot + Base_Height  ← primary target

    Also returns 21 EMA and 10-week MA current values for
    trailing stop seeding.

    Returns None if data unavailable — caller falls back gracefully.
    """
    ticker = symbol if symbol.endswith(".NS") else symbol + ".NS"
    try:
        df = yf.download(ticker, period="1y", interval="1d",
                         progress=False, threads=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 60:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"].dropna()
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        # Base window: last 60 sessions before pivot was formed
        # Approximate: find the lowest close in last 60 days
        base_low = float(close.tail(60).min())

        base_height = pivot - base_low
        measured_move = round(pivot + base_height, 2)
        base_height_pct = round((base_height / pivot) * 100, 2)

        # 21 EMA (daily)
        ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])

        # 10-week MA: resample to weekly, take last 10 weeks
        weekly_close = close.resample("W-FRI").last().dropna()
        ma10w = float(weekly_close.rolling(10).mean().iloc[-1]) if len(weekly_close) >= 10 else ema21

        # Current price for extension check
        current_price = float(close.iloc[-1])

        return {
            "base_low":        round(base_low, 2),
            "base_height":     round(base_height, 2),
            "base_height_pct": base_height_pct,
            "measured_move":   measured_move,
            "ema21_daily":     round(ema21, 2),
            "ma10_weekly":     round(ma10w, 2),
            "current_price":   current_price,
        }
    except Exception as e:
        print(f"    ⚠️ Could not fetch base geometry for {symbol}: {e}")
        return None


# ---------------------------------------------------------------
# STOP LOSS LOGIC
# ---------------------------------------------------------------

def compute_stop(entry: float, atr_pct: float, tier: str, quality: float) -> float:
    """
    Tier 1 + quality >= 8 → 1.0x ATR (tight, structure is clean)
    Tier 1 otherwise      → 1.5x ATR
    Tier 2+               → 2.0x ATR (base still forming)
    Hard floor: never stop closer than 1% below entry (avoid noise stops).
    Hard ceiling: never stop more than 8% below entry (too wide = bad setup).
    """
    if "Tier 1" in tier:
        mult = 1.0 if quality >= 8.0 else 1.5
    else:
        mult = 2.0

    atr_price = entry * (atr_pct / 100)
    raw_stop = entry - mult * atr_price

    # Apply floors and ceilings
    min_stop = entry * 0.92    # max 8% below entry
    max_stop = entry * 0.99    # at least 1% below entry
    return round(max(min_stop, min(raw_stop, max_stop)), 2)


# ---------------------------------------------------------------
# POSITION SIZING
# ---------------------------------------------------------------

def position_size(capital: float, entry: float, stop: float) -> dict:
    """
    Risk = 0.5% of capital.
    Units = risk_amount / risk_per_share.
    Hard cap: no single position > 20% of capital.
    """
    risk_amount     = capital * RISK_PCT
    risk_per_share  = entry - stop
    if risk_per_share <= 0:
        return {"error": "Stop >= entry."}

    raw_units   = int(risk_amount / risk_per_share)
    cap_units   = int((capital * 0.20) / entry)
    units       = min(raw_units, cap_units)

    if units <= 0:
        return {"error": "Position too small — increase capital or widen stop."}

    capital_used   = round(units * entry, 2)
    max_loss       = round(units * risk_per_share, 2)
    concentration  = round((capital_used / capital) * 100, 2)
    capped         = raw_units > cap_units

    return {
        "units":         units,
        "capital_used":  capital_used,
        "max_loss_rs":   max_loss,
        "concentration": concentration,
        "capped":        capped,
    }


# ---------------------------------------------------------------
# VOLUME DECISION ZONES  (3-zone, not binary)
# ---------------------------------------------------------------

def volume_decision(tier: str) -> dict:
    """
    Returns the three entry zones and their position size rules.
    Position Monitor will verify actual volume at execution time.
    """
    if "Tier 1" in tier:
        return {
            "zone_A": "> 1.8× average  →  Full position. Confirmed institutional participation.",
            "zone_B": "1.5–1.8× average →  Half position only. Add second half on follow-through day.",
            "zone_C": "< 1.5× average  →  DO NOT enter. Wait for next attempt with real volume.",
            "intraday_check": "Confirm zone A or B by 2:00pm IST before end-of-day entry.",
        }
    else:
        return {
            "zone_A": "N/A — base not ready for entry.",
            "zone_B": "N/A",
            "zone_C": "N/A",
            "intraday_check": "Monitor only. No entry until base tightens.",
        }


# ---------------------------------------------------------------
# TARGET STRUCTURE — VCP base height projection
# ---------------------------------------------------------------

def build_target_structure(entry: float, stop: float, pivot: float,
                            geo: dict, quality: float) -> dict:
    """
    Primary target = Measured Move (pivot + base height).
    This is the standard VCP / O'Neil projection.

    Trailing mechanism (not a fixed price target):
      - While stock is below 20% extension: trail on 21 EMA daily close.
      - Once > 20% above entry: trail on 10-week MA weekly close.

    Partial exit logic:
      - Take 1/3 off at 50% of measured move (lock in partial).
      - Hold remainder on trailing stop to let winner run.

    R-multiple is shown as context only — NOT used as the target.
    """
    R = entry - stop
    measured_move = geo["measured_move"]
    base_height_pct = geo["base_height_pct"]
    mid_target = round(entry + (measured_move - entry) * 0.50, 2)   # halfway point

    mm_gain_pct = round(((measured_move - entry) / entry) * 100, 2)
    mid_gain_pct = round(((mid_target - entry) / entry) * 100, 2)
    implied_R = round((measured_move - entry) / R, 2) if R > 0 else 0

    # Trailing stop guidance varies by quality
    if quality >= 8.0:
        trail_note = (
            "Trail on 21 EMA (daily close basis). Switch to 10-week MA once "
            "price extends >20% above entry. Exit only on a WEEKLY close below "
            "10-week MA — intraday violations do not count."
        )
        hold_note = "Let it run. High quality setups can extend 2–4× base height."
    elif quality >= 6.0:
        trail_note = (
            "Trail on 21 EMA (daily close). Do not switch to weekly MA — "
            "exit on first daily close below 21 EMA once above mid-target."
        )
        hold_note = "Target measured move. Don't overstay — exit discipline matters here."
    else:
        trail_note = (
            "Tight trail: exit on daily close below 21 EMA from day 5 onward. "
            "Low quality setup — take what the market gives, don't wait for full target."
        )
        hold_note = "Half position only. Take mid-target and re-evaluate."

    return {
        "base_height_pct":   base_height_pct,
        "base_low":          geo["base_low"],
        "mid_target":        mid_target,
        "mid_target_gain":   f"+{mid_gain_pct}%",
        "measured_move":     measured_move,
        "measured_move_gain": f"+{mm_gain_pct}%",
        "implied_R":         implied_R,
        "ema21_seed":        geo["ema21_daily"],
        "ma10w_seed":        geo["ma10_weekly"],
        "trail_rule":        trail_note,
        "hold_note":         hold_note,
        "partial_exit":      f"Sell 1/3 at mid-target (₹{mid_target}). "
                             f"Trail remainder on 21 EMA / 10-week MA.",
    }


# ---------------------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------------------

def run():
    print("\n⚡ TRADE EXECUTION ENGINE  (Entry Stage)\n")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ Not found: {INPUT_FILE}")
        print("   Run Master_Terminal.py first.")
        return

    df = pd.read_excel(INPUT_FILE)
    print(f"✅ {len(df)} setups loaded from Master Terminal.\n")

    while True:
        try:
            raw = input("💰 Enter total trading capital ₹ (e.g. 500000): ").strip()
            capital = float(raw.replace(",","").replace("₹","").strip())
            if capital > 0: break
        except ValueError:
            pass
        print("   Enter a valid number.")

    print(f"\n   Risk per trade: 0.5% = ₹{capital*0.005:,.0f} max loss\n")
    print("=" * 72)

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    trade_plans = []
    new_positions = []
    skipped = []

    for _, row in df.iterrows():
        symbol   = str(row.get("Symbol","")).strip()
        tier     = str(row.get("Operational Classification Tier","")).strip()
        opp      = parse_score(row.get("Opportunity","0"))
        readiness= parse_score(row.get("Readiness","0"))
        atr_pct  = parse_pct(row.get("14d ATR","0"))
        trigger  = str(row.get("Actionable Operational Trigger",""))
        edp_str  = str(row.get("Expected Days to Pivot (EDP)","?"))

        is_active = "ACTIVE TRIGGER" in trigger
        if not is_active:
            skipped.append((symbol, tier, "Not an active trigger — Tier 2 or structure not ready"))
            continue

        pivot = parse_pivot(trigger)
        if pivot <= 0:
            skipped.append((symbol, tier, "Could not parse pivot from trigger text"))
            continue

        quality = quality_composite(opp, readiness)

        print(f"  📐 Fetching base geometry for {symbol}...")
        geo = fetch_base_geometry(symbol, pivot)

        if geo is None:
            skipped.append((symbol, tier, "Could not download price data for base geometry"))
            continue

        entry = pivot
        stop  = compute_stop(entry, atr_pct, tier, quality)
        sizing = position_size(capital, entry, stop)
        if "error" in sizing:
            skipped.append((symbol, tier, sizing["error"]))
            continue

        targets  = build_target_structure(entry, stop, pivot, geo, quality)
        vol_rule = volume_decision(tier)

        # ── Console output ──────────────────────────────────────────
        print(f"\n{'─'*72}")
        print(f"  {symbol}   Quality: {quality}/10   EDP (pre-entry): {edp_str}")
        print(f"{'─'*72}")
        print(f"  Entry (breakout above)  : ₹{entry}")
        print(f"  Stop Loss               : ₹{stop}  "
              f"({'%.1f'%atr_pct}% ATR × {'1.0' if quality>=8 else '1.5' if 'Tier 1' in tier else '2.0'})")
        print(f"  Units                   : {sizing['units']} shares")
        print(f"  Capital deployed        : ₹{sizing['capital_used']:,.0f}  "
              f"({sizing['concentration']}% of portfolio)")
        print(f"  Max loss                : ₹{sizing['max_loss_rs']:,.0f}")
        if sizing["capped"]:
            print(f"  ⚠️  Units capped at 20% concentration limit")
        print(f"\n  BASE GEOMETRY")
        print(f"  Base low                : ₹{geo['base_low']}")
        print(f"  Base height             : {geo['base_height_pct']}% of pivot")
        print(f"  Mid-target (1/3 exit)   : ₹{targets['mid_target']}  "
              f"({targets['mid_target_gain']})")
        print(f"  Measured move target    : ₹{targets['measured_move']}  "
              f"({targets['measured_move_gain']}  / {targets['implied_R']}R)")
        print(f"\n  TRAILING STOP")
        print(f"  21 EMA (seed)           : ₹{targets['ema21_seed']}")
        print(f"  10-week MA (seed)       : ₹{targets['ma10w_seed']}")
        print(f"  Trail rule              : {targets['trail_rule']}")
        print(f"\n  VOLUME ENTRY ZONES")
        print(f"  {vol_rule['zone_A']}")
        print(f"  {vol_rule['zone_B']}")
        print(f"  {vol_rule['zone_C']}")
        print(f"  {vol_rule['intraday_check']}")
        print(f"\n  PARTIAL EXIT     : {targets['partial_exit']}")
        print(f"  HOLD GUIDANCE    : {targets['hold_note']}")
        print()

        plan_row = {
            "Symbol":            symbol,
            "Quality":           quality,
            "Entry":             entry,
            "Stop":              stop,
            "Units":             sizing["units"],
            "Capital (₹)":       sizing["capital_used"],
            "Max Loss (₹)":      sizing["max_loss_rs"],
            "Concentration %":   sizing["concentration"],
            "Base Low":          geo["base_low"],
            "Base Height %":     geo["base_height_pct"],
            "Mid Target":        targets["mid_target"],
            "Mid Target Gain":   targets["mid_target_gain"],
            "Measured Move":     targets["measured_move"],
            "MM Gain":           targets["measured_move_gain"],
            "Implied R":         targets["implied_R"],
            "21 EMA (seed)":     targets["ema21_seed"],
            "10w MA (seed)":     targets["ma10w_seed"],
            "Trail Rule":        targets["trail_rule"],
            "Vol Zone A":        vol_rule["zone_A"],
            "Vol Zone B":        vol_rule["zone_B"],
            "Vol Zone C":        vol_rule["zone_C"],
            "Partial Exit":      targets["partial_exit"],
            "Hold Note":         targets["hold_note"],
            "EDP (pre-entry)":   edp_str,
        }
        trade_plans.append(plan_row)

        # Position row for Position_Monitor.py
        new_positions.append({
            "symbol":          symbol,
            "entry_date":      today_str,
            "entry_price":     entry,
            "stop":            stop,
            "units":           sizing["units"],
            "base_low":        geo["base_low"],
            "measured_move":   targets["measured_move"],
            "mid_target":      targets["mid_target"],
            "ema21_seed":      targets["ema21_seed"],
            "ma10w_seed":      targets["ma10w_seed"],
            "quality":         quality,
            "status":          "OPEN",
            "partial_sold":    False,
            "notes":           "",
        })

    # ── Save outputs ─────────────────────────────────────────────
    if trade_plans:
        out = pd.DataFrame(trade_plans).sort_values("Quality", ascending=False)
        out.to_excel(OUTPUT_PLAN, index=False)
        print(f"✅ {len(trade_plans)} trade plans → {OUTPUT_PLAN}")

    if new_positions:
        pos_df_new = pd.DataFrame(new_positions)
        if os.path.exists(POSITIONS_FILE):
            existing = pd.read_csv(POSITIONS_FILE)
            # Don't duplicate if symbol already open
            existing_syms = existing[existing["status"]=="OPEN"]["symbol"].tolist()
            pos_df_new = pos_df_new[~pos_df_new["symbol"].isin(existing_syms)]
            combined = pd.concat([existing, pos_df_new], ignore_index=True)
        else:
            combined = pos_df_new
        combined.to_csv(POSITIONS_FILE, index=False)
        print(f"📦 {len(pos_df_new)} new positions → {POSITIONS_FILE}  "
              f"(Position_Monitor.py takes over from here)")

    if skipped:
        print(f"\nℹ️  {len(skipped)} skipped:")
        for sym, tier, reason in skipped:
            print(f"   {sym} ({tier[:30]}) — {reason}")

    # Persist to research_database
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""CREATE TABLE IF NOT EXISTS research_database (
            date TEXT, symbol TEXT, tier_lifecycle TEXT,
            opportunity_score REAL, readiness_score REAL,
            measurable_deficit TEXT, expected_days_to_pivot TEXT,
            primary_metrics_json TEXT,
            PRIMARY KEY (date, symbol))""")
        for row in trade_plans:
            conn.execute("""INSERT INTO research_database
                (date, symbol, opportunity_score, readiness_score, primary_metrics_json)
                VALUES (?,?,?,?,?)
                ON CONFLICT(date,symbol) DO UPDATE SET
                    opportunity_score=excluded.opportunity_score,
                    readiness_score=excluded.readiness_score,
                    primary_metrics_json=excluded.primary_metrics_json
            """, (today_str, row["Symbol"], row["Quality"], row["Quality"],
                  json.dumps({"entry": row["Entry"], "stop": row["Stop"],
                              "measured_move": row["Measured Move"]})))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️  DB write failed: {e}")

    print("\n⚡ Entry stage complete. Run Position_Monitor.py daily after entry.\n")


if __name__ == "__main__":
    run()