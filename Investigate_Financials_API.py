"""
Investigate_Financials_API.py

One-time investigation script for #70's continuation - settling with
real evidence, not assumption, whether yfinance genuinely provides:
1. Current Ratio, Interest Coverage inputs (via .info)
2. ROCE inputs (EBIT, Capital Employed - not a direct .info field)
3. Historical Revenue/Net Profit/EPS for CAGR calculation (.financials)
4. Quarterly EPS history for the last 8 quarters (.quarterly_earnings
   or .quarterly_income_stmt, since yfinance has changed this API
   across versions)
5. EBITDA margin and net profit margin trend data

Run this once, share the full output - it tells us exactly what's
real and buildable versus what would need a different data source
entirely, rather than guessing either way.
"""

import yfinance as yf

TEST_TICKER = "RBLBANK.NS"  # matches this system's own running example all night


def investigate():

    print()
    print("=" * 70)
    print(f"FINANCIALS API INVESTIGATION - {TEST_TICKER}")
    print("=" * 70)

    ticker = yf.Ticker(TEST_TICKER)

    print("\n--- 1. Additional .info fields (Current Ratio, ROCE inputs) ---")
    info = ticker.info
    for field in ["currentRatio", "quickRatio", "ebit", "totalDebt",
                  "returnOnAssets", "operatingMargins", "grossMargins"]:
        print(f"  {field}: {info.get(field)}")

    print("\n--- 2. Annual financials (.financials) - for Revenue/Profit CAGR ---")
    try:
        financials = ticker.financials
        print(f"  Shape: {financials.shape if financials is not None else 'None'}")
        if financials is not None and not financials.empty:
            print(f"  Available years: {list(financials.columns)}")
            print(f"  Available line items (first 15): {list(financials.index)[:15]}")
        else:
            print("  EMPTY or None - not available for this ticker")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n--- 3. Quarterly financials (.quarterly_financials) - for quarterly EPS ---")
    try:
        q_financials = ticker.quarterly_financials
        print(f"  Shape: {q_financials.shape if q_financials is not None else 'None'}")
        if q_financials is not None and not q_financials.empty:
            print(f"  Available quarters: {list(q_financials.columns)}")
            print(f"  Available line items (first 15): {list(q_financials.index)[:15]}")
        else:
            print("  EMPTY or None - not available for this ticker")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n--- 4. Quarterly earnings (.quarterly_earnings, older API) ---")
    try:
        q_earnings = ticker.quarterly_earnings
        print(f"  Result: {q_earnings}")
    except Exception as e:
        print(f"  ERROR (may be deprecated in this yfinance version): {e}")

    print("\n--- 5. Balance sheet (.balance_sheet) - for D/E trend, Current Ratio trend ---")
    try:
        balance_sheet = ticker.balance_sheet
        print(f"  Shape: {balance_sheet.shape if balance_sheet is not None else 'None'}")
        if balance_sheet is not None and not balance_sheet.empty:
            print(f"  Available years: {list(balance_sheet.columns)}")
            print(f"  Available line items (first 15): {list(balance_sheet.index)[:15]}")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n--- 6. Cash flow (.cashflow) - for Free Cash Flow ---")
    try:
        cashflow = ticker.cashflow
        print(f"  Shape: {cashflow.shape if cashflow is not None else 'None'}")
        if cashflow is not None and not cashflow.empty:
            print(f"  Available years: {list(cashflow.columns)}")
            print(f"  Available line items (first 15): {list(cashflow.index)[:15]}")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 70)
    print("Investigation complete - share this full output")
    print("=" * 70)


if __name__ == "__main__":
    investigate()