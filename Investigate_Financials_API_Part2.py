"""
Investigate_Financials_API_Part2.py

Follow-up to the first investigation - two remaining open questions:
1. Are Total Revenue / EBITDA lines present further down the full
   line-item list (only the first 15 of 38/28/44 were shown before)?
2. Is Current Ratio/EBIT genuinely unavailable everywhere, or was
   that specific to RBLBANK being a bank (banks don't have a
   traditional current-assets/EBIT structure)?
"""

import yfinance as yf

BANK_TICKER = "RBLBANK.NS"
NON_BANK_TICKER = "TCS.NS"  # a real, standard non-financial company for comparison


def investigate():

    print()
    print("=" * 70)
    print(f"COMPLETE LINE ITEMS - {BANK_TICKER}")
    print("=" * 70)

    ticker = yf.Ticker(BANK_TICKER)

    print("\n--- Complete .financials line items ---")
    financials = ticker.financials
    if financials is not None and not financials.empty:
        for item in financials.index:
            print(f"  {item}")

    print("\n--- Complete .cashflow line items ---")
    cashflow = ticker.cashflow
    if cashflow is not None and not cashflow.empty:
        for item in cashflow.index:
            print(f"  {item}")

    print("\n" + "=" * 70)
    print(f"NON-BANK COMPARISON - {NON_BANK_TICKER}")
    print("=" * 70)

    tcs = yf.Ticker(NON_BANK_TICKER)
    tcs_info = tcs.info

    print("\n--- .info fields (Current Ratio, EBIT) for a non-bank stock ---")
    for field in ["currentRatio", "quickRatio", "ebit", "returnOnAssets"]:
        print(f"  {field}: {tcs_info.get(field)}")

    print("\n--- .financials Total Revenue check for a non-bank stock ---")
    tcs_financials = tcs.financials
    if tcs_financials is not None and not tcs_financials.empty:
        for item in tcs_financials.index:
            if "revenue" in item.lower() or "ebitda" in item.lower():
                print(f"  {item}")

    print("\n" + "=" * 70)
    print("Investigation complete - share this full output")
    print("=" * 70)


if __name__ == "__main__":
    investigate()