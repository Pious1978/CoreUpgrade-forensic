import pandas as pd
import numpy as np
import yfinance as yf
import os
import re
from difflib import get_close_matches

# =====================================================
# CONFIG
# =====================================================
BASE_PATH = r"C:\Users\GS102\OneDrive\Research\Invest"
HOLDINGS_FILE = os.path.join(BASE_PATH, "Stocks_Holdings_Statement.xlsx")
OUTPUT_FILE = os.path.join(BASE_PATH, "UNIFIED_PORTFOLIO_V16.xlsx")

ALLOCATIONS = {
    "COMPOUNDERS": 25000,
    "GROWTH": 15000,
    "HIGH_RISK": 10000
}

# =====================================================
# MASTER TICKER MAP (FIXED + YOUR CORRECTIONS)
# =====================================================
TICKER_MAP = {
    # YOUR FIXES (IMPORTANT)
    "BLACKBOX": "BBOX",
    "AIA": "AIAENG",
    "AIA ENGINEERING": "AIAENG",
    "ANANT": "ANANTRAJ",
    "ANANT RAJ": "ANANTRAJ",
    "ECORECO": "ECORECO.BO",
    "ECO RECYCLING": "ECORECO.BO",

    # PREVIOUS FIXES
    "ANTONY WASTE HDG CELL LTD": "AWHCL",
    "CONTAINER CORP OF IND LTD": "CONCOR",
    "BIRLA COTSYN": "BIRLACORPN",
    "PG ELECTROPLAST LTD": "PGEL",
    "TRANSPORT CORPN OF INDIA": "TCI",
    "CG POWER AND IND SOL LTD": "CGPOWER",
    "GUJARAT MINERAL DEV CORP": "GMDCLTD",

    # LARGE CAPS
    "RELIANCE INDUSTRIES LTD": "RELIANCE",
    "HDFC BANK LTD": "HDFCBANK",
    "INFOSYS LTD": "INFY",
    "TCS": "TCS",
    "HINDUSTAN AERONAUTICS LTD": "HAL",
    "JSW INFRASTRUCTURE LTD": "JSWINFRA"
}

# =====================================================
# SAFE CLEAN
# =====================================================
def clean(x):
    if pd.isna(x):
        return ""
    return str(x).upper().strip()

# =====================================================
# HEADER DETECTION
# =====================================================
def detect_header(df_raw):
    best_row = 0
    best_score = 0

    for i in range(min(40, len(df_raw))):
        row = " ".join([str(x).lower() for x in df_raw.iloc[i].tolist()])

        keywords = ["stock", "symbol", "qty", "quantity", "avg", "price", "holding"]
        score = sum(k in row for k in keywords)

        if score > best_score:
            best_score = score
            best_row = i

    return best_row

# =====================================================
# LOAD HOLDINGS
# =====================================================
def load_holdings():
    try:
        raw = pd.read_excel(HOLDINGS_FILE, header=None)
        header = detect_header(raw)

        df = pd.read_excel(HOLDINGS_FILE, skiprows=header)
        df.columns = [clean(c).lower() for c in df.columns]

        stock_col = next((c for c in df.columns if "stock" in c or "name" in c), None)
        qty_col = next((c for c in df.columns if "qty" in c or "quantity" in c), None)
        avg_col = next((c for c in df.columns if "avg" in c or "price" in c), None)

        if not stock_col or not qty_col:
            print("❌ Missing required columns")
            return pd.DataFrame()

        df = df[[stock_col, qty_col, avg_col]].copy()
        df.columns = ["stock", "qty", "avg"]

        df["stock"] = df["stock"].apply(clean)
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
        df["avg"] = pd.to_numeric(df["avg"], errors="coerce").fillna(0)

        return df[df["qty"] > 0]

    except Exception as e:
        print("❌ Load error:", e)
        return pd.DataFrame()

# =====================================================
# TICKER RESOLVER (FIXED CORE)
# =====================================================
def resolve_ticker(name):
    name = clean(name)

    if name in TICKER_MAP:
        return TICKER_MAP[name]

    # fuzzy match safety
    match = get_close_matches(name, TICKER_MAP.keys(), n=1, cutoff=0.6)
    if match:
        return TICKER_MAP[match[0]]

    # fallback cleanup
    return name.split()[0]

# =====================================================
# PRICE ENGINE (ROBUST NS + BO)
# =====================================================
def get_price(name):
    symbol = resolve_ticker(name)

    # if already has exchange
    base = symbol.replace(".NS", "").replace(".BO", "")

    for suffix in [".NS", ".BO"]:
        try:
            t = yf.Ticker(base + suffix)
            hist = t.history(period="5d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1]), base + suffix
        except:
            continue

    # final fallback raw
    try:
        t = yf.Ticker(base)
        hist = t.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1]), base
    except:
        pass

    return None, base

# =====================================================
# WATCHLISTS
# =====================================================
COMPOUNDERS = [
    "DIXON","KAYNES","AMBER","LT","CONCOR","ADANIPORTS","HAL","BEL",
    "TATAPOWER","NTPC","BSE","HDFCAMC","INFY","SIEMENS","ABB","HCLTECH",
    "360ONE","RELIANCE","TCS","TITAN","M&M","SRF","AARTIIND","CAMS","PIIND"
]

GROWTH = [
    "TCS","INFY","HCLTECH","PERSISTENT","COFORGE","KPITTECH","TATAELXSI",
    "RELIANCE","LT","M&M","TITAN","MARUTI","NAVINFLUOR","DEEPAKNTR","360ONE","AARTIIND"
]

HIGH_RISK = [
    "AVALON","PGEL","SYRMA","AMBER","DCXINDIA","JSWINFRA","IRCON","SUZLON",
    "ANGELONE","POLICYBZR","HAPPSTMNDS","BLACKBOX","COCHINSHIP","INOXWIND"
]

# =====================================================
# SCORE ENGINE
# =====================================================
def score(symbol):
    try:
        t = yf.Ticker(symbol + ".NS")
        h = t.history(period="1y")

        if h.empty:
            return 0

        r = h["Close"].pct_change().mean() * 252
        v = h["Close"].pct_change().std() * np.sqrt(252)
        mom = h["Close"].pct_change(63).iloc[-1]
        trend = 1 if h["Close"].iloc[-1] > h["Close"].rolling(200).mean().iloc[-1] else 0

        return (r*2 + mom*1.5 + trend) / (v + 0.2)

    except:
        return 0

# =====================================================
# BUILD PORTFOLIO
# =====================================================
def build(universe, capital):
    out = []

    for s in universe:
        sc = score(s)
        price, ticker = get_price(s)

        if price is None:
            continue

        alloc = capital / len(universe)
        qty = int(alloc // price)

        out.append({
            "Stock": s,
            "Ticker": ticker,
            "Score": round(sc, 2),
            "Qty": qty,
            "Invested": round(qty * price, 2),
            "LTP": price
        })

    return pd.DataFrame(out)

# =====================================================
# REVIEW EXISTING PORTFOLIO
# =====================================================
def review(df):
    res = []

    for _, r in df.iterrows():
        price, ticker = get_price(r["stock"])
        if price is None:
            continue

        invested = r["qty"] * r["avg"]
        current = r["qty"] * price

        pnl = (current - invested) / invested * 100 if invested else 0

        action = "BOOK PROFIT" if pnl > 40 else "CUT / REVIEW" if pnl < -20 else "HOLD"

        res.append({
            "Stock": r["stock"],
            "Ticker": ticker,
            "PnL%": round(pnl, 2),
            "Action": action
        })

    return pd.DataFrame(res)

# =====================================================
# MAIN
# =====================================================
def run():
    print("\n🧠 V16 UNIFIED PORTFOLIO BRAIN (FINAL FIXED)")
    print("=" * 80)

    holdings = load_holdings()

    print("\n📊 BUILDING PORTFOLIO...")

    comp = build(COMPOUNDERS, ALLOCATIONS["COMPOUNDERS"])
    grow = build(GROWTH, ALLOCATIONS["GROWTH"])
    risk = build(HIGH_RISK, ALLOCATIONS["HIGH_RISK"])

    print("\n🟢 COMPOUNDERS")
    print(comp)

    print("\n🟡 GROWTH")
    print(grow)

    print("\n🔴 HIGH RISK")
    print(risk)

    if not holdings.empty:
        print("\n📊 HOLDINGS REVIEW")
        print(review(holdings))

    with pd.ExcelWriter(OUTPUT_FILE) as writer:
        comp.to_excel(writer, sheet_name="COMPOUNDERS", index=False)
        grow.to_excel(writer, sheet_name="GROWTH", index=False)
        risk.to_excel(writer, sheet_name="HIGH_RISK", index=False)
        review(holdings).to_excel(writer, sheet_name="REVIEW", index=False)

    print(f"\n✔ Saved → {OUTPUT_FILE}")

if __name__ == "__main__":
    run()