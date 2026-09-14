# Manual Trading Lifecycle

Addresses #92 - the explicit, documented system boundary for this
project's real, working trading system.

## This document describes a genuinely different thing than `ARCHITECTURE_RULES.md`

`ARCHITECTURE_RULES.md` and the rest of `docs/` describe the
OMS/EMS/`PortfolioControlPlane` architecture (Gates 1-7,
`research/validation`, `governance/audit_controls`). That architecture
is real code, but it is **confirmed, genuinely inert** - `run_cycle()`
is never instantiated, `certify.py` is never called, and the real
paper broker doesn't implement the OMS's own `BrokerAdapter` protocol.
It describes a system this project could grow into, not the one that
runs tonight.

This document describes the system that actually runs: a decision-
support pipeline that ends at a `TradePlan`, with the person - not
the system - executing every real order in their own broker terminal.
**There is no requirement for this system to submit an order, and no
OMS/EMS is required for it to work.** That is a deliberate boundary,
not a temporary limitation.

## The real lifecycle, mapped to the real, current codebase

| # | Stage | Real, current implementation |
|---|---|---|
| 1 | Market Observation | `HistoricalBhavcopies/` (raw NSE bhav copies) → `bhav_to_parquet_converter.py` |
| 2 | Market Context | `Market_Regime_Engine.py` - regime, breadth, India VIX, distribution days, follow-through days |
| 3 | Research Evidence | `RelativeStrengthEngine.py`, `Sector_Strength_Ranker.py`, and the discovery scanners (`Consolidation_Scanner.py`, `Hybrid_Alpha_Scanner.py`, `Reversal_Exhaustion_Scanner.py`, and others) - all write to `scanner_factors` |
| 4 | Setup | The scanners' own pattern and pivot output, in `setup_pivots` |
| 5 | Trade Thesis | `TradePlan_Builder.py`'s `build_trade_thesis()` - a real summary generated from the actual factor values found, not a template |
| 6 | Risk Plan | `Risk_Positioning_Engine.py` - position sizing, stop, ATR, sector/concentration caps |
| 7 | **Trade Plan** | `TradePlan_Builder.py` - the full, structured object (`ResearchEvidence` / `Setup` / `TradeThesis` / `RiskPlan` / `EntryPlan` / `ExitPlan` / `Provenance`), persisted with a real `trade_plan_id` |
| 8 | **Human Decision** | `HumanTradeDecision.py` - `ACCEPT` / `REJECT` / `DEFER`, recorded against the real `trade_plan_id` |
| 9a | *(REJECT/DEFER path)* | No trade. The decision is still recorded - this is what eventually lets the system learn where discretionary judgment added or cost value. |
| 9b | *(ACCEPT path)* Manual Broker Execution | **Outside this system, deliberately.** The person places the real order in their own broker terminal (Zerodha, Upstox, or similar). |
| 10 | Actual Fill | `ActualTrade.py` - the real fill, recorded against the `ACCEPT` decision. `compute_execution_quality()` directly reconciles the planned entry (the pivot) against what was actually filled. |
| 11 | Position | `Trade_Journal.py` - the `positions` / `trade_journal` tables |
| 12 | Position Monitoring | `Live_Execution_Monitor.py`, `Stock_Lookup.py` - live conviction scoring, execution/event risk, topping risk, and the rest of tonight's detection work |
| 13 | Exit Decision | The person's own judgment, informed by what Live_Execution_Monitor.py/Stock_Lookup.py surface (stop/target proximity, topping risk, momentum breakdown, and so on) |
| 14 | Manual Exit | **Outside this system, deliberately** - the person's own broker terminal, same as entry |
| 15 | Exit Fill | `Trade_Journal.py` - the recorded exit (`realized_pnl`, `exit_date`) |
| 16 | Closed Trade | `trade_journal` table, `status = 'CLOSED'` |
| 17 | Outcome Attribution | Partially built: `ActualTrade.py`'s `compute_execution_quality()` (execution failure) and `HumanTradeDecision.py`'s `get_decision_history()` (human-selection failure) each answer part of this. **Honest gap**: no single, unified report yet combines all three failure modes (research / execution / human-selection) into one view - see `#111`/`#112` in the pending architectural list. |
| 18 | Learning / Validation | `alerts.log` (`#78`, outcome tracking - `VALID_BREAKOUT`/`STOP_BREACHED`/`TARGET_1_HIT`/`TARGET_2_HIT`) and `SwingBacktest/`. **Honest gap**: sample sizes remain genuinely too small for statistically meaningful setup-level calibration (`#76`/`#77`, confirmed blocked). |

## What this system deliberately does not do

- It does not submit orders. There is no broker adapter requirement.
- It does not require an OMS or EMS to function correctly.
- It does not assume every `TradePlan` will be accepted, or every
  acceptance perfectly executed - `HumanTradeDecision` and
  `ActualTrade` exist specifically to make those two gaps visible and
  measurable, not to close them by fiat.

## Why the ActualTrade / HumanTradeDecision split matters

The system's own belief (a `TradePlan`'s research evidence and score)
and what actually happened (a real, human-made decision, followed by
a real fill) are recorded as genuinely separate objects. This makes
three distinct failure modes possible to tell apart, rather than every
losing trade looking the same:

1. **Research failure** - the system said BUY, the thesis was wrong.
2. **Execution failure** - the setup was genuinely good, but the fill
   didn't match the plan (`ActualTrade.py`'s `compute_execution_quality()`
   makes this directly measurable).
3. **Human-selection failure** - the system was right, but the trade
   was rejected, and the stock ran without you
   (`HumanTradeDecision.py`'s `get_decision_history()` makes this
   directly queryable, once enough decisions accumulate).