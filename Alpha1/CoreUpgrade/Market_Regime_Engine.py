import pandas as pd
import numpy as np


class MarketRegimeEngine:

    def __init__(self):

        self.INDEX_WHITELIST = {
            "^NSEI",
            "NSEI",
            "NIFTY",
            "NIFTY50",
            "BANKNIFTY",
            "NSEBANK",
            "NIFTYMIDCAP"
        }


    def check_is_index(self, ticker_clean):

        return ticker_clean.upper() in self.INDEX_WHITELIST



    def calculate_roc20(self, df):

        if len(df) < 21:
            return 0.0

        previous = float(df["close"].iloc[-21])
        current = float(df["close"].iloc[-1])

        if previous == 0:
            return 0.0

        return ((current / previous)-1)*100



    def calculate_advance_decline(self, returns):

        advances = (returns > 0).sum()
        declines = (returns < 0).sum()

        if declines == 0:
            return 2.0

        return advances / declines



    def evaluate_market_breadth_and_regime(
            self,
            nifty_df,
            breadth_data,
            all_stocks_returns):


        close = float(nifty_df["close"].iloc[-1])


        sma50 = float(
            nifty_df["sma_50"].iloc[-1]
        )

        sma200 = float(
            nifty_df["sma_200"].iloc[-1]
        )


        nifty_above_50 = close > sma50
        nifty_above_200 = close > sma200


        roc20 = self.calculate_roc20(nifty_df)


        b20 = breadth_data.get(
            "breadth_20",0)

        b50 = breadth_data.get(
            "breadth_50",0)

        b200 = breadth_data.get(
            "breadth_200",0)



        ad_ratio = self.calculate_advance_decline(
            all_stocks_returns
        )



        # =========================
        # SCORE ENGINE
        # =========================


        score_b200 = min(
            100,
            (b200/60)*100
        )*0.25


        score_b50 = min(
            100,
            (b50/50)*100
        )*0.20


        score_b20 = min(
            100,
            (b20/50)*100
        )*0.10



        trend_score = 0

        if nifty_above_50:
            trend_score +=50

        if nifty_above_200:
            trend_score +=50


        score_trend = trend_score*0.20



        roc_score = max(
            0,
            min(
                100,
                ((roc20+10)/20)*100
            )
        )


        score_roc = roc_score*0.10



        if ad_ratio >=1.5:

            ad_score=100

        elif ad_ratio<=0.7:

            ad_score=0

        else:

            ad_score = (
                (ad_ratio-0.7)/0.8
            )*100



        score_ad = ad_score*0.15



        composite = round(
            score_b200+
            score_b50+
            score_b20+
            score_trend+
            score_roc+
            score_ad,
            2
        )



        # =========================
        # STATE MACHINE
        # =========================


        if (
            composite>=70
            and b200>=45
            and nifty_above_200
        ):

            regime="CONFIRMED_UPTREND"



        elif (
            nifty_above_50
            and roc20>2
            and (
                b20>50
                or b50>40
            )
        ):

            regime="EARLY_RECOVERY"



        elif (
            nifty_above_200
            and (
                ad_ratio<0.8
                or b200<40
            )
        ):

            regime="DISTRIBUTION"



        elif (
            composite<35
            and not nifty_above_50
            and not nifty_above_200
        ):

            regime="BEAR"



        else:

            regime="CHOPPY_ACCUMULATION"



        # =========================
        # CONFIDENCE
        # =========================


        if composite>=75:

            confidence="HIGH"

        elif composite>=55:

            confidence="MEDIUM"

        else:

            confidence="LOW"



        exposure={

            "CONFIRMED_UPTREND":1.00,

            "EARLY_RECOVERY":0.50,

            "CHOPPY_ACCUMULATION":0.60,

            "DISTRIBUTION":0.25,

            "BEAR":0.25

        }.get(
            regime,
            0.25
        )



        return {


            "regime":regime,

            "confidence":confidence,

            "composite_score":composite,

            "breadth_20":round(b20,2),

            "breadth_50":round(b50,2),

            "breadth_200":round(b200,2),

            "advance_decline_ratio":
                round(ad_ratio,2),

            "position_multiplier":
                exposure

        }
