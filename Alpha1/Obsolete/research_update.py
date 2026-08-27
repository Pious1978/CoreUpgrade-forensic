import pandas as pd
import os
import re
import math
import yfinance as yf
import numpy as np

# --- Configuration ---
TRADE_FILE = 'Trade.xlsx'
MAX_RISK_INR = 500
CAPITAL = 200000

def extract_forensic_data(text):
    """Uses Regex to find price levels in Gemini's response."""
    data = {}
    patterns = {
        'entry': r"Entry Zone:\s*₹?\s*([\d,.]+)",
        'value': r"Value Zone:\s*₹?\s*([\d,.]+)",
        'sl': r"Stop Loss:\s*₹?\s*([\d,.]+)",
        'exit': r"Exit Levels:\s*₹?\s*([\d,.]+)"
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = float(match.group(1).replace(',', ''))
            data[key] = val
    return data

def update_master_sheet(symbol, results):
    """Calculates risk parameters and commits to Excel with safety checks."""
    if not os.path.exists(TRADE_FILE):
        # Create a new file with headers if it doesn't exist
        df = pd.DataFrame(columns=['Share Name', 'Quantity to Buy', 'Total Investment'])
        df.to_excel(TRADE_FILE, index=False)

    try:
        df = pd.read_excel(TRADE_FILE, sheet_name='Sheet1')
        df.columns = [str(c).strip() for c in df.columns]

        # --- NAN & ZERO RISK PROTECTION ---
        entry = results.get('entry', 0)
        sl = results.get('sl', 0)
        
        if math.isnan(entry) or math.isnan(sl) or entry == 0:
            print(f"❌ Calculation Aborted: Prices for {symbol} are NaN or Zero.")
            return

        risk_ps = round(entry - sl, 2)
        
        if risk_ps <= 0:
            print(f"⚠️ Risk Error: Stop Loss (₹{sl}) must be below Entry (₹{entry}).")
            return

        # Safe integer conversion - Fixes the ValueError
        qty = int(MAX_RISK_INR // risk_ps)
        total_inv = round(qty * entry, 2)

        new_data = {
            'Share Name': symbol,
            'Portfolio Capital (₹)': CAPITAL,
            'Entry Zone': entry,
            'Value Zone (Nifty 24k)': results.get('value', 0),
            'Stop Loss Price': sl,
            'Exit Levels': results.get('exit', 0),
            'Risk per Share': risk_ps,
            'Quantity to Buy': qty,
            'Total Investment': total_inv,
            'Risk per Trade': MAX_RISK_INR
        }

        # Update or Append Logic
        mask = df['Share Name'].astype(str).str.upper().str.strip() == symbol.upper()
        
        if mask.any():
            print(f"🔄 Updating existing research for {symbol}...")
            idx = df[mask].index[0]
            for col, val in new_data.items():
                if col in df.columns:
                    df.at[idx, col] = val
        else:
            print(f"➕ Adding new research entry for {symbol}...")
            if 'Sr No' in df.columns:
                new_data['Sr No'] = df['Sr No'].max() + 1 if not df.empty else 1
            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)

        while True:
            try:
                df.to_excel(TRADE_FILE, index=False)
                print(f"✅ Trade.xlsx Updated successfully.")
                break
            except PermissionError:
                input("⚠️ File is OPEN! Please close 'Trade.xlsx' and press Enter to retry...")

    except Exception as e:
        print(f"❌ Excel Update Error: {e}")

def run():
    print("\n" + "="*65)
    print("PIYOOSH'S 4-PHASE QUANT ANALYST (v4.0 - FIXED)")
    print("="*65)
    
    raw_name = input("Enter Stock Name (e.g. NMDC): ").upper().strip()
    if not raw_name: return
    
    # --- AUTO-TICKER CORRECTION ---
    symbol = raw_name if ('.' in raw_name) else f"{raw_name}.NS"

    print(f"📊 Fetching Phase 1 data for {symbol}...")
    t = yf.Ticker(symbol)
    hist = t.history(period="1d")

    if hist.empty:
        print(f"❌ Error: Could not find market data for {symbol}. Try adding .NS manually.")
        return

    cmp = round(hist['Close'].iloc[-1], 2)
    print(f"✅ Connection Stable | CMP: ₹{cmp}")

    # 1. Provide the Prompt
    prompt = f"""
Act as a Senior Equity Research Analyst. Perform a 4-Phase deep-dive of: {symbol}.
Phase 1: Strategic/Moat | Phase 2: Financial Forensic | Phase 3: Cash Flow | Phase 4: Valuation.

At the end of your analysis, provide these EXACT lines:
Entry Zone: {cmp}
Value Zone: [Estimated price]
Stop Loss: [Set 5% below Entry]
Exit Levels: [Set 20% Target]
"""
    print(f"\n[STEP 1] COPY THIS PROMPT FOR GEMINI:\n{'-'*50}\n{prompt}\n{'-'*50}")

    # 2. Get Input
    print(f"\n[STEP 2] Paste Gemini's analysis below.")
    print("Type 'DONE' on a new line when finished (or 'CANCEL' to abort):")

    lines = []
    while True:
        l = input()
        if l.upper() == "DONE": break
        if l.upper() == "CANCEL": return
        lines.append(l)
    
    full_text = "\n".join(lines)
    extracted = extract_forensic_data(full_text)
    
    if len(extracted) < 4:
        print("\n❌ Error: Missing price points in pasted text. Did you include the 'EXACT lines'?")
    else:
        print(f"\n📥 Data Extracted: Entry ₹{extracted['entry']} | SL ₹{extracted['sl']}")
        confirm = input("\nCommit to Trade.xlsx? (y/n): ").lower()
        if confirm == 'y':
            update_master_sheet(symbol, extracted)

if __name__ == "__main__":
    run()