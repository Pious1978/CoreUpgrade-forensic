"""
core/Live_Price_Engine.py
---------------------------------------------------------
Real-Time Intraday Price + RVOL Engine
"""

import yfinance as yf
import pandas as pd
import time
import logging

# Real, direct fix: "possibly delisted; no price data found" is
# yfinance's own generic, hardcoded message printed on ANY failed
# download - it fires for rate-limiting, transient Yahoo-side issues,
# or thin intraday coverage on recent listings, just as often as an
# actual delisting. It's misleading noise, not a real diagnostic -
# confirmed directly by KOTAKBANK (one of NSE's most liquid, actively
# traded stocks) appearing in this list. Silenced at the source
# (yfinance's own logger) rather than filtered after printing.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 1.5

# Real, direct fix for tickers that fail persistently, cycle after
# cycle (confirmed directly: the same ~10 tickers failed identically
# across three consecutive 60-second cycles) - after this many
# consecutive failures, stop retrying every single cycle and cool down
# instead, periodically re-checking rather than wasting 3 full retries
# with real, growing delays on a ticker that's very likely to fail
# again regardless.
CONSECUTIVE_FAILURE_COOLDOWN_THRESHOLD = 3
COOLDOWN_SECONDS = 600  # 10 minutes - long enough to skip wasted retries, short enough to recover once the real issue (rate limit, transient outage) clears

_failure_state = {}  # ticker -> {"consecutive_failures": int, "cooldown_until": float or None}


class LivePriceEngine:


    @staticmethod
    def get_live_quote(ticker):

        start=time.time()

        state = _failure_state.get(ticker)
        if state and state.get("cooldown_until") and time.time() < state["cooldown_until"]:
            # Real, direct skip - this ticker has failed
            # CONSECUTIVE_FAILURE_COOLDOWN_THRESHOLD times in a row
            # recently; no point spending 3 more real, delayed retries
            # on it right now. Returns the same honest "ERROR" result
            # a failed download would have given, just without the
            # wasted time and noisy repeated attempts.
            return LivePriceEngine.empty(ticker, round(time.time()-start, 2))

        symbol = (
            ticker
            if ticker.endswith(".NS")
            else ticker+".NS"
        )

        for attempt in range(MAX_RETRIES):

            try:

                df = yf.download(
                    symbol,
                    period="5d",
                    interval="5m",
                    progress=False
                )


                latency=round(
                    time.time()-start,
                    2
                )


                if df.empty:

                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_BASE_DELAY_SECONDS * (attempt + 1))
                        continue

                    return LivePriceEngine._record_failure_and_return_empty(ticker, start)


                if isinstance(df.columns,pd.MultiIndex):

                    df.columns=[
                        c[0].lower()
                        for c in df.columns
                    ]

                else:

                    df.columns=[
                        c.lower()
                        for c in df.columns
                    ]



                df=df.dropna()


                today=df.index[-1].date()


                today_data=df[
                    df.index.date==today
                ]


                previous=df[
                    df.index.date < today
                ]



                ltp=float(
                    today_data["close"].iloc[-1]
                )


                today_open=float(
                    today_data["open"].iloc[0]
                )


                # Today's high/low so far - derived from the same
                # already-fetched intraday bars used for RVOL, no extra
                # API call needed. Used for candle-body-ratio fakeout
                # detection: a genuine breakout should close near its
                # session high, not spike and fall back.
                today_high=float(
                    today_data["high"].max()
                )


                today_low=float(
                    today_data["low"].min()
                )


                prev_close=float(
                    previous["close"].iloc[-1]
                )



                current_volume=float(
                    today_data["volume"].iloc[-1]
                )



                avg_volume=float(
                    today_data["volume"]
                    .iloc[:-1]
                    .mean()
                )



                rvol=round(
                    current_volume/avg_volume,
                    2
                ) if (avg_volume>0 and current_volume>0) else 1.0



                gap=round(
                    (
                    (today_open-prev_close)
                    /
                    prev_close
                    )*100,
                    2
                )



                # Real, direct reset - a successful fetch means whatever
                # was causing earlier failures has cleared, so this
                # ticker gets a clean slate rather than staying flagged.
                if ticker in _failure_state:
                    del _failure_state[ticker]

                return {

                    "ticker":ticker,

                    "ltp":ltp,

                    "open":today_open,

                    "high":today_high,

                    "low":today_low,

                    "previous_close":prev_close,

                    "gap_pct":gap,

                    "volume":current_volume,

                    "rvol":rvol,

                    "latency":latency,

                    "status":"SUCCESS"

                }


            except Exception:

                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BASE_DELAY_SECONDS * (attempt + 1))
                    continue

        return LivePriceEngine._record_failure_and_return_empty(ticker, start)



    @staticmethod
    def _record_failure_and_return_empty(ticker, start):
        """
        Real, single, shared tracking point for BOTH genuine failure
        paths (an empty DataFrame, or a raised exception) - after
        CONSECUTIVE_FAILURE_COOLDOWN_THRESHOLD real, final failures in
        a row, this ticker cools down instead of being retried every
        single cycle.
        """

        state = _failure_state.setdefault(ticker, {"consecutive_failures": 0, "cooldown_until": None})
        state["consecutive_failures"] += 1
        if state["consecutive_failures"] >= CONSECUTIVE_FAILURE_COOLDOWN_THRESHOLD:
            state["cooldown_until"] = time.time() + COOLDOWN_SECONDS

        return LivePriceEngine.empty(
            ticker,
            round(time.time()-start,2)
        )



    @staticmethod
    def empty(ticker,latency):

        return {

            "ticker":ticker,

            "ltp":0,

            "open":0,

            "high":0,

            "low":0,

            "previous_close":0,

            "gap_pct":0,

            "volume":0,

            "rvol":1,

            "latency":latency,

            "status":"ERROR"

        }