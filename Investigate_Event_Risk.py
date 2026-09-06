"""
Investigate_Event_Risk.py

#75 investigation - does yfinance provide real earnings dates,
corporate actions, or ex-dividend dates? Checking .calendar and
.earnings_dates specifically, since these are the most likely
candidates based on general yfinance knowledge, but not assumed to
work until verified here.
"""

import yfinance as yf

TEST_TICKER = "RBLBANK.NS"


def investigate():

    print()
    print("=" * 70)
    print(f"EVENT RISK INVESTIGATION - {TEST_TICKER}")
    print("=" * 70)

    ticker = yf.Ticker(TEST_TICKER)

    print("\n--- 1. .calendar (upcoming earnings date, typically) ---")
    try:
        calendar = ticker.calendar
        print(f"  Result: {calendar}")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n--- 2. .earnings_dates (historical + upcoming earnings dates) ---")
    try:
        earnings_dates = ticker.earnings_dates
        print(f"  Result:\n{earnings_dates}")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n--- 3. .actions (dividends + splits combined) ---")
    try:
        actions = ticker.actions
        print(f"  Shape: {actions.shape if actions is not None else 'None'}")
        if actions is not None and not actions.empty:
            print(actions.tail(10))
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n--- 4. .splits (stock splits/bonus history) ---")
    try:
        splits = ticker.splits
        print(f"  Result: {splits}")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n" + "=" * 70)
    print("Investigation complete - share this full output")
    print("=" * 70)


if __name__ == "__main__":
    investigate()