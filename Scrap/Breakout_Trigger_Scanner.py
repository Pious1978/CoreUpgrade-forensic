"""
Breakout_Trigger_Scanner.py
-------------------------------------------------------------------------
Phase 5: Tactical Breakout Execution Monitor
Pure execution engine. Reads strictly from SQLite `execution_candidates`.
"""

import os
import time
import sqlite3
import logging
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, time as dt_time
import sys
import io

logging.getLogger('yfinance').setLevel(logging.CRITICAL)
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
elif hasattr(sys.stdout, "buffer"): sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from core.config import (
    TRADE_PLAN_EXCEL, PARQUET_CACHE_DIR, DB_PATH, RVOL_TRIGGER_LIMIT, 
    PIVOT_BUFFER_PCT, RISK_REWARD_RATIO, RISK_PCT, CONVICTION_WEIGHTS, REGIME_MULTIPLIERS
)

POLL_INTERVAL_SECONDS = 60
MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)

PROXIMITY_FILTER = {"BULL": 0.90, "NEUTRAL": 0.93, "BEAR": 0.95}
REGIME_LIMITS = {"BULL": 250, "NEUTRAL": 150, "BEAR": 75}

def get_current_market_regime() -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT regime FROM market_regime ORDER BY date DESC LIMIT 1", conn)
        conn.close()
        return df['regime'].iloc[0].upper() if not df.empty else "NEUTRAL"
    except Exception: return "NEUTRAL"

def print_alert(alert: dict):
    sep, dash = "=" * 66, "-" * 66
    print(f"\n🚨 {sep}\n  [{alert['Timestamp']}]  {alert['Ticker']} (Pattern: {alert['Pattern']})\n{dash}")
    print(f"  STATUS        : {alert['Status']}")
    print(f"  Current Price : ₹{alert['Price']}  |  Trigger: ₹{alert['Trigger']}  |  Ext: {alert['Ext%']}%")
    print(f"  Intraday RVOL : {alert['RVOL']}×\n{dash}")
    if "EXTENDED" in alert["Status"]:
        print(f"  ❌ SIZING REJECTED — Entry over-extended. Wait for pullback.")
    else:
        print(f"  📥 Entry        : ₹{alert['Entry']}\n  🛑 Stop Loss    : ₹{alert['Stop_Loss']}")
        print(f"  🎯 Target 1     : ₹{alert['Target_1']}  (+{alert['Dist_T1%']}% away)")
        print(f"  🚀 Target 2     : ₹{alert['Target_2']}  (+{alert['Dist_T2%']}% away)\n  ⚖️  Remaining R  : {alert['Remaining_R']}×\n{dash}")
        if alert["Units"] > 0: print(f"  📦 Units        : {alert['Units']} shares\n  💰 Capital Used : ₹{alert['Capital_Used']:,.0f} ({alert['Concentration']}%)\n  📉 Max Loss     : ₹{alert['Max_Loss_Rs']:,.0f}")
        else: print(f"  📦 Position Size: {alert['Sizing_Note']}")
    print(f"{dash}\n  🏆 CONVICTION   : {alert['Conviction_Score']}/100 — {alert['Conviction_Tier']} (Regime: {alert['Regime']} ×{alert['Regime_Mult']})")
    print(f"  🧠 Tier         : {alert['Tier']}\n🚨 {sep}\n")

def calc_position_size(capital: float, entry: float, stop: float) -> dict:
    if capital <= 0 or entry <= 0 or stop >= entry: return {"units": 0, "capital_used": 0, "max_loss": 0, "concentration": 0, "note": "Cannot size."}
    risk_amount, risk_per_share = capital * RISK_PCT, entry - stop
    raw_units, cap_units = int(risk_amount / risk_per_share), int((capital * 0.20) / entry)
    units = min(raw_units, cap_units)
    if units <= 0: return {"units": 0, "capital_used": 0, "max_loss": 0, "concentration": 0, "note": "Too small."}
    return {"units": units, "capital_used": round(units * entry, 2), "max_loss": round(units * risk_per_share, 2), "concentration": round((units * entry / capital) * 100, 2), "note": ("⚠️ Capped at 20%." if raw_units > cap_units else "")}

def execute_live_monitoring_loop(capital: float, active_targets: dict, triggered_cache: set, regime: str, regime_multiplier: float) -> tuple:
    new_triggers, failed_downloads, scanned_count = set(), set(), 0

    for ticker, data in active_targets.items():
        try:
            live_df = yf.download(f"{data['clean_ticker']}.NS", period="1d", interval="5m", progress=False, threads=False)
            if live_df.empty:
                failed_downloads.add(data['clean_ticker'])
                continue
            
            scanned_count += 1
            if isinstance(live_df.columns, pd.MultiIndex): live_df.columns = live_df.columns.get_level_values(0)

            curr_px = float(live_df['Close'].iloc[-1])
            curr_vol = float(live_df['Volume'].iloc[-1])
            avg_vol = live_df['Volume'].iloc[:-1].mean() if len(live_df) > 1 else curr_vol
            live_rvol = curr_vol / avg_vol if avg_vol > 0 else 1.0

            stop_loss = curr_px - (1.5 * data['atr_14'])
            if stop_loss >= curr_px: stop_loss = curr_px * 0.95
            if curr_px - stop_loss <= 0: continue

            t1 = curr_px + ((curr_px - stop_loss) * RISK_REWARD_RATIO)
            t2 = curr_px + ((curr_px - stop_loss) * RISK_REWARD_RATIO * 2.0)
            rem_r = ((t1 - curr_px)/curr_px*100) / (((curr_px - stop_loss)/curr_px*100) + 1e-8)
            ext_pct = ((curr_px - data['trigger']) / data['trigger']) * 100

            if not (curr_px >= data['trigger'] and live_rvol >= RVOL_TRIGGER_LIMIT): continue

            status = "⚠️ BREAKOUT EXTENDED" if (curr_px > data['trigger']*(1.0+PIVOT_BUFFER_PCT/100.0) or rem_r < 1.2) else "🔥 VALID BREAKOUT"
            sizing = calc_position_size(capital, curr_px, stop_loss)
            
            lead_score = ((data['rs'] * 0.70) + (data['trend'] * 0.30)) * 10.0
            struct_score = ((data['comp']*0.30) + (data['acc']*0.30) + (data['volat']*0.20) + (data['deliv']*0.20)) * 10.0
            tape_score = max(0.0, min(10.0, max(0.0, live_rvol * 3.0)) - max(0.0, (ext_pct - 1.0) * 1.5))
            risk_score = max(0.0, (min(10.0, rem_r * 3.5) * 0.60) + ((10.0 if ((curr_px - stop_loss)/curr_px*100) <= 8.0 else 7.0) * 0.40) - (3.0 if "EXTENDED" in status else 0.0))
            
            raw_conv = ((lead_score * CONVICTION_WEIGHTS["leadership"]) + (struct_score * CONVICTION_WEIGHTS["structure"]) + (tape_score * CONVICTION_WEIGHTS["tape"]) + (risk_score * CONVICTION_WEIGHTS["risk"])) * 10.0
            conv_100 = min(100.0, max(0.0, round(raw_conv * regime_multiplier, 0)))
            c_tier = "A+ Conviction" if conv_100 >= 85 else "A Conviction" if conv_100 >= 75 else "B Conviction" if conv_100 >= 65 else "Watchlist (C)"

            alert = {
                "Ticker": ticker, "Timestamp": datetime.now().strftime("%H:%M:%S"), "Pattern": data['pattern'], 
                "Price": round(curr_px, 2), "Trigger": round(data['trigger'], 2), "Ext%": round(ext_pct, 2), "RVOL": round(live_rvol, 2), 
                "Status": status, "Entry": round(curr_px, 2), "Stop_Loss": round(stop_loss, 2), "Target_1": round(t1, 2), "Target_2": round(t2, 2), 
                "Dist_T1%": round((t1-curr_px)/curr_px*100, 1), "Dist_T2%": round((t2-curr_px)/curr_px*100, 1), "Remaining_R": round(rem_r, 2), 
                "Units": sizing["units"], "Capital_Used": sizing["capital_used"], "Max_Loss_Rs": sizing["max_loss"], "Concentration": sizing["concentration"], 
                "Sizing_Note": sizing["note"], "Tier": data['tier'], "Conviction_Score": int(conv_100), "Conviction_Tier": c_tier,
                "Regime": regime, "Regime_Mult": regime_multiplier
            }

            if f"{ticker}_{status}" not in triggered_cache:
                new_triggers.add(f"{ticker}_{status}")
                print_alert(alert)
                pd.DataFrame([alert]).to_csv(os.path.join(os.path.dirname(TRADE_PLAN_EXCEL), "ACTIVE_BREAKOUT_ALERTS.csv"), mode="a", header=not os.path.exists(os.path.join(os.path.dirname(TRADE_PLAN_EXCEL), "ACTIVE_BREAKOUT_ALERTS.csv")), index=False)
            time.sleep(0.05)  
        except Exception: continue

    return new_triggers, failed_downloads, scanned_count

if __name__ == "__main__":
    print("=" * 66)
    print("🎯  BREAKOUT TRIGGER REAL-TIME STREAMING ENGINE")
    print("=" * 66)

    try: capital = float(input("\n💰 Enter your trading capital ₹ (e.g. 100000): ").strip() or 100000.0)
    except ValueError: capital = 100000.0

    current_regime = get_current_market_regime()
    regime_mult = REGIME_MULTIPLIERS.get(current_regime, 0.95)
    
    print(f"\n[INFO] Capital: ₹{capital:,.0f} | Risk/trade: ₹{capital * RISK_PCT:,.0f}")
    print(f"[INFO] Overnight Market Regime: {current_regime} (Multiplier: {regime_mult}x)")

    try:
        conn = sqlite3.connect(DB_PATH)
        df_exec = pd.read_sql("SELECT * FROM execution_candidates WHERE Date = (SELECT MAX(Date) FROM execution_candidates)", conn)
        conn.close()
    except Exception:
        print("[-] Could not load execution_candidates from SQLite. Run Pivot Consensus first.")
        raise SystemExit

    if df_exec.empty:
        print("[-] 0 execution candidates generated for today. Halting scanner.")
        raise SystemExit

    # Sort by Top N
    limit = REGIME_LIMITS.get(current_regime, 150)
    df_exec = df_exec.sort_values(by='Composite_Score', ascending=False).head(limit)

    watch_multiplier = PROXIMITY_FILTER.get(current_regime, 0.93)
    max_dist = (1.0 - watch_multiplier) * 100

    print("\n    [+] DIAGNOSTIC: PROXIMITY GAP EVALUATION")
    print("    " + "-"*60)
    
    active_targets = {}
    for _, row in df_exec.iterrows():
        ticker = row['Ticker']
        clean_t = str(ticker).replace('.NS', '').replace('^', '')
        pq_path = os.path.join(PARQUET_CACHE_DIR, f"{clean_t}.parquet")
        
        if os.path.exists(pq_path):
            try:
                df = pd.read_parquet(pq_path, columns=['close'])
                prior_close = float(df['close'].iloc[-1])
                trigger = float(row['Pivot']) * (1.0 + PIVOT_BUFFER_PCT / 100.0)
                dist = ((trigger - prior_close) / trigger) * 100
                
                print(f"    {clean_t:15} Close:₹{prior_close:>7.2f} | Trigger:₹{trigger:>7.2f} | Gap:{dist:>6.2f}% | ATR:₹{row['ATR14']:>6.2f}")

                if dist <= max_dist:
                    active_targets[ticker] = {
                        'clean_ticker': clean_t, 'trigger': trigger, 'atr_14': float(row['ATR14']), 
                        'pattern': row['Pattern'], 'tier': row['Tier'], 'rs': row['RS_Percentile'], 
                        'trend': row['Trend_Alignment'], 'comp': row['Base_Compression'], 
                        'acc': row['Accumulation_Ratio'], 'volat': row['Volatility_Score'], 'deliv': row['Delivery_Score']
                    }
            except Exception: continue

    print(f"\n    Execution Candidates Provided : {len(df_exec):>4}")
    print(f"    Near Pivot (<{max_dist:.1f}% dist)      : {len(active_targets):>4}\n")

    triggered_today = set()
    now = datetime.now()
    if now.time() < MARKET_OPEN:
        print(f"[*] Pre-market. First scan at 9:15 AM IST.")
        while datetime.now().time() < MARKET_OPEN: time.sleep(15)

    while True:
        if datetime.now().time() > MARKET_CLOSE:
            print(f"\n[*] Market closed. {len(triggered_today)} total alerts fired today.")
            break
            
        start_time = time.time()
        try:
            new_alerts, missing, scanned = execute_live_monitoring_loop(capital, active_targets, triggered_today, current_regime, regime_mult)
            triggered_today.update(new_alerts)
            
            elapsed = time.time() - start_time
            sleep_for = max(0, POLL_INTERVAL_SECONDS - elapsed)
            print(f"\r{' '*75}", end='\r')  
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle: {elapsed:.1f}s | Next: {sleep_for:.0f}s | Scanned: {scanned} | Triggers: {len(triggered_today)} | API Fails: {len(missing)} ", end='')
            if missing: print(f" (Missing e.g., {', '.join(list(missing)[:3])})", end='')
        except KeyboardInterrupt:
            print("\n\n[+] Scanner terminated safely by user.")
            break
        except Exception: pass
        time.sleep(sleep_for)
