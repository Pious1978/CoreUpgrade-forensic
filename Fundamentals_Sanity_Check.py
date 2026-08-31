"""
Fundamentals_Sanity_Check.py

The Monday check this whole session has been waiting on. Before
trusting Compounder_Scanner.py, HighRisk_Scanner.py, SIP_Allocator.py,
or Stock_Lookup.py's fundamentals check against the full universe,
confirm yfinance's .info actually returns real, sensible values for a
few well-known large-caps first.

Deliberately small and quick - just the exact fields our scanners
actually use (sector, industry, ROE, debt/equity, profit margin,
revenue growth), for three stocks whose real numbers are well known
enough to sanity-check by eye:

- TCS: IT services, should show high ROE (historically ~40-50%),
  very low debt (IT services is typically asset-light, low-leverage)
- RELIANCE: diversified conglomerate (energy/retail/telecom), moderate
  ROE, meaningfully more debt than TCS given its capital-intensive
  businesses
- HDFCBANK: a bank - banks report fundamentally different ratios
  (debt/equity is structurally not meaningful the same way for a
  bank, since deposits aren't "debt" in the normal sense) - worth
  seeing what yfinance actually returns here specifically, since a
  bank is a genuinely different case from the other two.

Nothing here gets trusted until the actual output is checked against
what a real, informed person would expect.
"""

import yfinance as yf

TEST_STOCKS = ["TCS", "RELIANCE", "HDFCBANK"]


def run():

    print()
    print("=" * 70)
    print("FUNDAMENTALS SANITY CHECK - REAL YFINANCE DATA")
    print("=" * 70)

    for ticker in TEST_STOCKS:

        print(f"\n{'-'*60}")
        print(f"{ticker}")
        print(f"{'-'*60}")

        try:
            info = yf.Ticker(f"{ticker}.NS").info

            if not info:
                print("[-] .info returned empty - no data at all for this ticker.")
                continue

            sector = info.get("sector")
            industry = info.get("industry")
            roe = info.get("returnOnEquity")
            debt_to_equity = info.get("debtToEquity")
            profit_margin = info.get("profitMargins")
            revenue_growth = info.get("revenueGrowth")

            print(f"  Sector              : {sector}")
            print(f"  Industry            : {industry}")
            print(f"  ROE                 : {roe*100:.1f}%" if roe is not None else "  ROE                 : MISSING")
            print(f"  Debt/Equity         : {debt_to_equity}" if debt_to_equity is not None else "  Debt/Equity         : MISSING")
            print(f"  Profit Margin       : {profit_margin*100:.1f}%" if profit_margin is not None else "  Profit Margin       : MISSING")
            print(f"  Revenue Growth      : {revenue_growth*100:.1f}%" if revenue_growth is not None else "  Revenue Growth      : MISSING")

            missing = sum(1 for v in [sector, industry, roe, debt_to_equity, profit_margin, revenue_growth] if v is None)
            if missing > 0:
                print(f"  [!] {missing} of 6 fields missing for {ticker}")

        except Exception as e:
            print(f"[-] Fetch failed entirely for {ticker}: {e}")

    print("\n" + "=" * 70)
    print("Check these numbers against what you'd expect before trusting")
    print("anything built on top of this data at full scale.")
    print("=" * 70)


if __name__ == "__main__":
    run()