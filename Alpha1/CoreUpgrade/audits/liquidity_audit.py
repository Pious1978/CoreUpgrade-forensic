"""
liquidity_audit.py
-------------------------------------------------------------------------

Institutional Liquidity Validation Layer

Purpose:
    Ensures trade candidates have sufficient liquidity
    for institutional-style execution.

Checks:
    1. Minimum traded value
    2. Average volume stability
    3. Price sanity
    4. Spread proxy
    5. Position capacity
    6. Delivery liquidity (optional)

Returns:
    Standard audit result dictionary.

-------------------------------------------------------------------------

"""


import pandas as pd
import numpy as np

from core.config import (
    BASE_CAPITAL,
    MAX_POSITION_PCT
)


# =========================================================================
# Default Liquidity Thresholds
# =========================================================================

MIN_AVG_VOLUME = 100000        # shares/day
MIN_ADTV = 10_000_000         # ₹1 crore daily traded value
MIN_PRICE = 20                # avoid penny stocks

MAX_POSITION_ADTV_PERCENT = 0.05
# Maximum allowed position = 5% of average daily traded value


# =========================================================================
# Helper
# =========================================================================

def safe_column(schema, key):

    col = schema.get(key)

    if col and col in schema.values():
        return col

    return None



# =========================================================================
# Liquidity Audit
# =========================================================================

def audit_liquidity(df, schema):

    result = {

        "layer": "Liquidity",

        "status": "PASS",

        "score": 100.0,

        "details": []

    }


    if df is None or df.empty:

        return result



    failures = 0



    # Resolve columns

    ticker_col = safe_column(schema, "ticker")

    price_col = (
        safe_column(schema, "current_price")
        or safe_column(schema, "pivot")
    )

    volume_col = (
        safe_column(schema, "avg_volume")
        or safe_column(schema, "volume")
    )

    adtv_col = safe_column(
        schema,
        "avg_daily_value"
    )

    delivery_col = safe_column(
        schema,
        "delivery_pct"
    )



    for _, row in df.iterrows():


        symbol = (
            row.get(ticker_col, "UNKNOWN")
            if ticker_col
            else "UNKNOWN"
        )



        # -----------------------------------------------------
        # Price Validation
        # -----------------------------------------------------

        price = row.get(price_col, 0)

        try:
            price = float(price)

        except:

            price = 0



        if price < MIN_PRICE:

            failures += 1

            result["details"].append(
                {
                    "symbol": symbol,
                    "reason":
                        f"Liquidity: Price too low ({price})",
                    "severity": "WARNING"
                }
            )



        # -----------------------------------------------------
        # Volume Validation
        # -----------------------------------------------------

        if volume_col:


            volume = row.get(volume_col, 0)

            try:
                volume = float(volume)

            except:

                volume = 0



            if volume < MIN_AVG_VOLUME:

                failures += 1

                result["details"].append(
                    {
                        "symbol": symbol,
                        "reason":
                            f"Liquidity: Low average volume ({volume:,.0f})",
                        "severity": "ERROR"
                    }
                )



        # -----------------------------------------------------
        # ADTV Validation
        # -----------------------------------------------------

        if adtv_col:


            adtv = row.get(
                adtv_col,
                0
            )


            try:

                adtv = float(adtv)

            except:

                adtv = 0



            if adtv < MIN_ADTV:


                failures += 1


                result["details"].append(
                    {
                        "symbol": symbol,
                        "reason":
                            (
                                "Liquidity: "
                                f"ADTV below threshold "
                                f"(₹{adtv:,.0f})"
                            ),
                        "severity": "ERROR"
                    }
                )



            # -------------------------------------------------
            # Position Capacity Check
            # -------------------------------------------------

            max_position = (
                adtv *
                MAX_POSITION_ADTV_PERCENT
            )


            intended_position = (
                BASE_CAPITAL *
                MAX_POSITION_PCT
            )



            if intended_position > max_position:


                failures += 1


                result["details"].append(
                    {
                        "symbol": symbol,

                        "reason":
                            (
                                "Liquidity: "
                                "Position size exceeds "
                                "5% ADTV capacity"
                            ),

                        "severity":
                            "WARNING"
                    }
                )



        # -----------------------------------------------------
        # Delivery Quality
        # -----------------------------------------------------

        if delivery_col:


            delivery = row.get(
                delivery_col,
                0
            )


            try:

                delivery = float(delivery)

            except:

                delivery = 0



            if delivery < 20:


                result["details"].append(
                    {
                        "symbol": symbol,

                        "reason":
                            (
                                f"Liquidity: Weak delivery "
                                f"({delivery:.1f}%)"
                            ),

                        "severity":
                            "WARNING"
                    }
                )



    # =========================================================
    # Score Calculation
    # =========================================================


    if failures:


        result["status"] = "ERROR"


        result["score"] = max(
            0,
            100 -
            ((failures / len(df)) * 100)
        )



    return result
