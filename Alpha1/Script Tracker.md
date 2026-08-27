6:30 PM – 7:00 PM IST

python Pipeline\_DAG\_Executor.py

python Risk\_Positioning\_Engine.py

python Live\_Execution\_Monitor.py



RS\_Accel\_Delivery\_Trend.py

&#x20;(NSE officially archives the institutional MTO.DAT delivery logs by 6:15 PM. Running this first creates today's snapshot entry inside rs\_delivery\_history.db, calculating your time-aligned market-wide RS rankings.)



9:30pm 10:00 PM

Master\_Terminal.py



7:00 PM – 9:30 PM IST

Hybrid\_Alpha\_Scanner1.py

Consolidation\_Scanner1.py

Earnings\_Gap\_Scanner.py

Emerging\_Leader\_Scanner.py



This process pulls the raw logs from Steps 2, 3, 4, and 5, reconciles the metrics, handles your newly patched graduated decision engine parameters, and writes the master tactical watch tables (COMPOSITE\_ALPHA\_OUTPUT.xlsx and MASTER\_OUTPUT.xlsx)



Next Morning 9:08

Launch the terminal at 9:08 AM IST (during the pre-market settlement window).



This gives the script time to launch, prompt you for your daily CAPITAL metric, perform its multi-source mesh compilation across all three asset sheets, connect to the Yahoo Finance API cluster, and sit waiting on a warm thread. The exact millisecond the clock strikes 9:15:00 AM, your intraday 5-minute tracking loop will instantly capture alpha extensions without a single bar of execution lag.



Breakout\_Trigger\_Scanner.py



===============================================================================



EVENING (after 3:30pm, market closed)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Master\_Terminal.py

&#x20;       ↓

Trade\_Execution\_Engine.py



Because: market is closed, no breakouts happening.

You're preparing the trade plan for tomorrow.

Output → TRADE\_EXECUTION\_PLAN.xlsx with entry levels,

stops, targets, position sizes ready before open.



NEXT MORNING (9:00am–9:15am, before open)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakout\_Trigger\_Scanner.py



Because: market is about to open.

It reads COMPOSITE\_ALPHA\_OUTPUT.xlsx and

TRADE\_EXECUTION\_PLAN.xlsx and monitors live

for the actual breakout trigger with volume.

Run this INSTEAD of Trade\_Execution\_Engine —

not after it, they don't chain together.



DURING MARKET HOURS (9:15am–3:30pm)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakout\_Trigger\_Scanner.py stays running

until you get an alert or market closes.



EVENING                          MORNING

───────────────────────────────────────────────────────

RS\_Accel\_Delivery\_Trend.py       Breakout\_Trigger\_Scanner.py

&#x20;       ↓                                ↓

Consolidation\_Scanner1.py        fires alert with full

&#x20;       ↓                        trade plan when pivot

Master\_Terminal.py               + volume confirms

&#x20;       ↓

Trade\_Execution\_Engine.py

&#x20;       ↓

Review TRADE\_EXECUTION\_PLAN.xlsx

Set price alerts

Sleep



=============

Ecosystem 1 — Swing Trading

Philosophy: Find compressed setups, enter on breakout with volume, manage with rules.



EVENING ROUTINE (after 3:30pm)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 0 │ Position\_Monitor.py          ← STARTS HERE

&#x20;       │ Checks all open positions

&#x20;       │ Output → POSITION\_STATUS.xlsx

&#x20;       │ Verdict per stock:

&#x20;       │   🚨 EXIT      → close the position tonight

&#x20;       │   💰 PARTIAL   → sell 1/3, update stop

&#x20;       │   📈 TRAIL ↑   → raise your stop level

&#x20;       │   ✅ HOLD      → nothing to do, continue

&#x20;       │

&#x20;       │ ⚠️ Act on EXIT/PARTIAL verdicts FIRST

&#x20;       │    before scanning for anything new

&#x20;       │

&#x09; RS\_Accel\_Delivery\_Trend.py

Step 1 │ Consolidation\_Scanner1.py

&#x20;       │ Scans full NSE universe

&#x20;       │ Output → Institutional\_Breakout\_Report.xlsx

&#x20;       │

Step 2 │ Master\_Terminal.py

&#x20;       │ Reads Institutional\_Breakout\_Report.xlsx

&#x20;       │ Internally runs RS\_Accel\_Delivery\_Trend.py

&#x20;       │ Output → COMPOSITE\_ALPHA\_OUTPUT.xlsx

&#x20;       │

Step 3 │ Trade\_Execution\_Engine.py

&#x20;       │ Reads COMPOSITE\_ALPHA\_OUTPUT.xlsx

&#x20;       │ You enter capital → generates trade plans

&#x20;       │ Output → TRADE\_EXECUTION\_PLAN.xlsx

&#x20;       │

&#x20;       │ ⚠️ Capital available = total capital

&#x20;       │    MINUS capital already in open positions

&#x20;       │    (Position\_Monitor shows this in status)

&#x20;       │

Step 4 │ \[Manual] Review TRADE\_EXECUTION\_PLAN.xlsx

&#x20;       │ Pick 3-5 highest quality setups

&#x20;       │ Set price alerts at pivot levels

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXT MORNING (9:00am, before open)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 5 │ Breakout\_Trigger\_Scanner.py

&#x20;       │ Reads COMPOSITE\_ALPHA\_OUTPUT.xlsx

&#x20;       │ Live 5-min monitoring during market hours

&#x20;       │ Alerts on valid breakout + fakeout detection

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SINGLE STOCK DEEP DIVE (any time, optional)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

&#x20;       │ Pullback\_Analyzer.py  → "Is this pullback buyable?"

&#x20;       │ Tradef.py             → "Quick signal + fundamental check"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WEEKEND (once a week)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

&#x20;       │ Base\_Building\_Scanner.py

&#x20;       │ Builds broader watchlist candidates

&#x20;       │ Feed interesting names into next week's

&#x20;       │ Consolidation\_Scanner1.py manually

&#x20;       │

&#x20;       │ Factor\_Validation.py

&#x20;       │ Once enough history accumulates (\~8 weeks)

&#x20;       │ Checks whether RS acceleration is still

&#x20;       │ predicting forward returns

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━





Ecosystem 2 — Value / Position Investing

Philosophy: Find business inflection + institutional entry before the chart is obvious. Hold months, not days.

MONTHLY SCREEN (first weekend of month)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1 │ Fundamental.py

&#x20;       │ Screens NSE for quality + valuation factors

&#x20;       │ Output → quality shortlist (\~50-100 names)

&#x20;       │

Step 2 │ Emerging\_Leader\_Scanner.py

&#x20;       │ Runs on fundamental shortlist

&#x20;       │ Finds stocks in "emergence phase" before

&#x20;       │ institutions make them obvious

&#x20;       │ Output → emerging candidates (\~20-30 names)

&#x20;       │

Step 3 │ Hybrid\_Alpha\_Scanner1.py

&#x20;       │ Cross-sectional ranking engine

&#x20;       │ Ranks the emerging candidates by RS,

&#x20;       │ liquidity flow, industry strength

&#x20;       │ Output → ranked top 10-15

&#x20;       │

Step 4 │ Earnings\_Gap\_Scanner.py

&#x20;       │ Check which of the top 15 have earnings

&#x20;       │ catalyst or acceleration angle

&#x20;       │ Output → highest conviction 5-8 names

&#x20;       │

Step 5 │ \[Manual] Build position plan

&#x20;       │ Use Pullback\_Analyzer.py on each finalist

&#x20;       │ to find the right entry timing

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONDITIONAL (only when regime = RISK\_OFF)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

&#x20;       │ Bear\_Market\_Scanner.py

&#x20;       │ Replaces Steps 2-3 above when market is weak

&#x20;       │ Finds high R:R recovery candidates

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ONGOING VALIDATION (monthly)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

&#x20;       │ Factor\_Validation.py

&#x20;       │ Checks whether your factors are still

&#x20;       │ predicting forward returns

&#x20;       │ Run once a month on accumulated history



1. Base\_Building\_Scanner.py - Is institutional accumulation scanner, finds Mark Minervini / William O'Neil style VCP bases before breakout. It is designed to find, Stocks in strong uptrends that are building tight consolidation bases (VCPs) just below breakout levels while institutions quietly accumulate shares. 'Better for stock selection/ watchlist creation' , will find market leaders, strong sectors, proper Stage-2 bases.

✔ VCP detection (partial but solid)

✔ Minervini trend filters

✔ Weekly alignment

✔ RS percentile ranking

✔ Volume dry-up

✔ Pivot proximity

✔ Liquidity filter

✔ Industry/theme RS layering

On weekend



**-----------------**

Breakout\_Trigger\_Scanner.py -

**✔ Breakout detection**

**✔ Fake breakout detection**

**✔ Entry timing zone**

**✔ Accumulation phase signal (light version)**

**✔ RS acceleration (light version)**





**-----------------**

2\. Hybrid\_Alpha\_Scanner1.py - Most advanced and most “institutional-grade” system so far. It is not a scanner in the usual sense anymore — it is a market regime + cross-sectional alpha ranking engine. It builds a market-wide institutional ranking system using RS acceleration, liquidity flows, industry strength, and breakout quality — adjusted dynamically by market regime.



**-----------------**

3\. Emerging\_Leader\_Scanner.py - high-conviction stock discovery engine designed to find potential future market leaders before they become obvious momentum stocks. Unlike your VCP or Base Building scanners that look for established setups, this scanner is hunting for stocks in the "emergence phase"—when institutions may just be starting to accumulate them. Best for discovering unknown future winners 1–3 months before breakout



**-----------------**

4\. Earnings\_Gap\_Scanner.py - a full institutional-grade multi-factor equity ranking engine that includes earnings as just one small component.       Institutional Leadership + Momentum + Earnings Composite Engine. Stage-2 leadership detector, Pre-breakout + breakout hybrid system, VCP + momentum + earnings fusion model.



**-----------------**

5\. Consolidation\_Scanner.py - This one is actually the cleanest and most pure “setup scanner” in your entire system. Unlike the others (which mix fundamentals, RS, earnings, scoring, etc.), this file is focused on a single idea, it scans NSE stocks to find tight bases + low volatility + volume dry-up + breakout proximity setups (pure pre-breakout compression plays). Find stocks compressing tightly and preparing for an imminent move, is more selective and trend-focused. The Consolidation Scanner is more of a volatility compression + breakout readiness detector. Better for timing, will find tight coils, volatility squeezes, setups that may move within days.



**-----------------**

6\. Trend\_Following\_Scanner.py - It finds high-quality breakout stocks in strong uptrends using RS, VCP, volume, and Minervini trend filters — then ranks them into trade-ready setups with entry, stop-loss, and targets



**-----------------**

4\. Cup\_and\_Handle.py - This script is a multi-regime institutional Cup \& Handle scanner for Indian stocks (NSE) with a weekend/weekday adaptive universe + theme tagging layer. “High-quality Cup \& Handle breakout setups with institutional characteristics”





**-----------------**



1\. Pullback\_Analyzer.py - Is a single-stock quality inspector, Think of it as the script you run after a scanner has already found a stock, checking is this pullback healthy enough to buy, and what is the trade plan



**-----------------**

2\. SwingVCP.py - Volatility Contraction Pattern, scanner that checks whether a stock is showing tightening price action near a breakout zone.

No entry/exit strategy

No risk management

No scoring vs market

No portfolio integration

No multi-stock scanning



SwingVCP.py → scoring + compression grading system. “Is this forming a VCP / base setup?”

👉 Think of it as:

SwingVCP = dashboard

Swing.py = engine component



**-----------------**

3\. Swing.py - Clean reusable function for embedding. A trend + breakout analyzer with interpretation layer. It will analyze and tell "Should I look at this stock or not?"



**-----------------**

5\. Fundamental.py - it’s a full institutional-grade factor investing + valuation + portfolio optimizer engine built in layers. It converts raw Indian stock market + financial statement data Which stocks to own, how much to allocate, and why (quant-driven)



**-----------------**

6\. Tradef.py - is a more advanced version of your earlier trading engine, because it adds a fundamental scoring layer on top of your technical + market regime system. It analyzes a stock using technical trends + NIFTY regime + basic fundamentals + your portfolio holdings, then generates a buy/accumulate/watch/avoid signal with trade levels.



**-----------------**

7\. Trade\_Execution\_Engine.py (Ex Analyst)- single-stock trade decision engine

which has Missing



\-----------------

1.Master\_Terminal.py - It sits above your other heavy scanners and gives a quick actionable shortlist based on simple breakout + momentum + portfolio context. It combines, my current portfolio holdings, the entire NSE universe, a simple breakout scoring model and outputs “Which stocks are near breakout + strong enough to act on right now”



**-----------------**

2\. Bear\_Market\_Scanner.py - It has opposite philosophy of your trend/VCP scanners. Instead of chasing momentum and breakouts, it hunts deep pullback “value buys” in bear/weak markets with risk-reward filters and relative strength protection. It scans NSE stocks to find: “Stocks that have already fallen hard, but are NOT structurally dead, and now offer a high R:R bounce/recovery opportunity.”







==============

