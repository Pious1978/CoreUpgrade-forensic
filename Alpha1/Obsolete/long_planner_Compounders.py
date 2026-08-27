import pandas as pd
import numpy as np
import yfinance as yf
import datetime

# =========================
# CONFIG
# =========================
WATCHLIST = [
    "DIXON", "KAYNES", "AMBER",
    "LT", "CONCOR", "ADANIPORTS",
    "HAL", "BEL",
    "TATAPOWER", "NTPC",
    "BSE",
    "HDFCAMC",
    "INFY",          # Infosys
    "SIEMENS", "ABB",
    "HCLTECH",       # HCL Technologies
    "360ONE",        # 360 ONE WAM
    "RELIANCE", "TCS",
    "TITAN", "M&M",
    "SRF",
    "AARTIIND",      # Aarti Industries
    "NAM-INDIA",     # Nippon AMC
    "CAMS",
    "GNFC", "PIIND",
    "DEEPAKNTR", "NAVINFLUOR"
]

BASE_CAPITAL = 25000
TRADE_FILE = "compounder_v7.xlsx"


# =========================
# 1. DATA ENGINE
# =========================
def get_data(symbol):
    try:
        t = yf.Ticker(symbol + ".NS")
        hist = t.history(period="5y")

        if hist.empty or len(hist) < 200:
            return None, None

        info = t.info
        return hist, info

    except:
        return None, None


# =========================
# 2. QUALITY FILTER
# =========================
def quality_gate(info):
    if not info:
        return False

    roe = info.get("returnOnEquity", 0)
    debt = info.get("debtToEquity", 999)
    margin = info.get("profitMargins", 0)

    return not (
        roe < 0.12 or
        debt > 150 or
        margin < 0.05
    )


# =========================
# 3. COMPOUNDER SCORE ENGINE v7
# =========================
def compounder_score(hist, info):
    close = hist["Close"]

    cagr = (close.iloc[-1] / close.iloc[0]) ** (1/5) - 1
    volatility = close.pct_change().std() * np.sqrt(252)

    ma200 = close.rolling(200).mean().iloc[-1]
    trend = 1 if close.iloc[-1] > ma200 else 0

    drawdown = (close / close.cummax() - 1).min()

    roe = info.get("returnOnEquity", 0.15)
    margins = info.get("profitMargins", 0.1)
    revenue_growth = info.get("revenueGrowth", 0.10)

    score = (
        (cagr * 120) +
        (roe * 80) +
        (margins * 60) +
        (revenue_growth * 70) +
        (trend * 40) +
        (drawdown * 50)
    ) / (volatility + 0.2)

    return round(score, 2)


# =========================
# 4. POSITION SIZING
# =========================
def size_position(score, price, volatility):
    base_risk = BASE_CAPITAL * 0.08

    risk_adjusted = base_risk * (score / 50)
    risk_adjusted = risk_adjusted / max(volatility, 0.15)

    qty = int(risk_adjusted / price)
    invest = qty * price

    return qty, invest


# =========================
# 5. PORTFOLIO BUILDER
# =========================
def build_portfolio():

    results = []
    cash_left = BASE_CAPITAL

    for s in WATCHLIST:

        hist, info = get_data(s)
        if hist is None:
            continue

        if not quality_gate(info):
            continue

        score = compounder_score(hist, info)

        price = hist["Close"].iloc[-1]
        volatility = hist["Close"].pct_change().std() * np.sqrt(252)

        qty, invest = size_position(score, price, volatility)

        cash_left -= invest

        action = (
            "STRONG COMPOUNDER BUY" if score > 60 else
            "BUY" if score > 35 else
            "ACCUMULATE" if score > 20 else
            "WATCH"
        )

        results.append({
            "Stock": s,
            "Score": score,
            "Price": round(price, 2),
            "Qty": qty,
            "Invested": round(invest, 2),
            "Action": action
        })

    return pd.DataFrame(results), cash_left


# =========================
# 6. OUTPUT
# =========================
def run():

    df, cash = build_portfolio()

    print("\n" + "="*70)
    print("🧠 COMPOUNDER BRAIN v7 (UPDATED WATCHLIST)")
    print("="*70)

    for _, r in df.iterrows():
        print(f"""
Stock: {r['Stock']}
Score: {r['Score']}
Price: ₹{r['Price']}
Qty: {r['Qty']}
Invested: ₹{r['Invested']}
Action: {r['Action']}
-------------------------
        """)

    print(f"\n💰 Remaining Cash: ₹{round(cash,2)}")


if __name__ == "__main__":
    run()