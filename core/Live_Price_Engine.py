"""
Live_Price_Engine.py
---------------------------------------------------------
Real-Time Intraday Price + RVOL Engine
"""

import yfinance as yf
import pandas as pd
import time


class LivePriceEngine:


    @staticmethod
    def get_live_quote(ticker):

        start=time.time()

        symbol = (
            ticker
            if ticker.endswith(".NS")
            else ticker+".NS"
        )

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

                return LivePriceEngine.empty(
                    ticker,
                    latency
                )


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



            return {

                "ticker":ticker,

                "ltp":ltp,

                "open":today_open,

                "previous_close":prev_close,

                "gap_pct":gap,

                "volume":current_volume,

                "rvol":rvol,

                "latency":latency,

                "status":"SUCCESS"

            }



        except Exception:


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

            "previous_close":0,

            "gap_pct":0,

            "volume":0,

            "rvol":1,

            "latency":latency,

            "status":"ERROR"

        }
