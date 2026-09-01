"""
Tax_Report.py

#57 - Tax awareness. Real trade facts and calculations, deliberately
kept separate from core/tax_config.py's tax law/rates - see that
file's docstring for why.

Reads BOTH trade_journal (full, single-tranche exits) and
trade_journal_exits (partial exits, from #26 - a position closed in
multiple tranches, each potentially with its own holding period and
therefore its own STCG/LTCG classification). Every real, closed
tranche is classified individually - a single position sold in two
tranches at different times can genuinely have one tranche as STCG and
the other as LTCG.

Aggregates by Indian financial year (April 1 - March 31) and
classification, and applies the LTCG exemption correctly: only against
a POSITIVE net LTCG for that year, never against a loss, and never
carried across years.

This estimates; it does not file. See core/tax_config.py for the
"verify before relying on this" note.
"""

import sqlite3
import pandas as pd
from datetime import datetime

from core.config import DB_PATH
from core.tax_config import (
    LTCG_HOLDING_PERIOD_DAYS, STCG_RATE_PCT, LTCG_RATE_PCT,
    LTCG_ANNUAL_EXEMPTION_RS, CESS_RATE_PCT, FY_START_MONTH,
    CONFIG_VERSION, CONFIG_LAST_VERIFIED
)


def get_financial_year(date):
    """Indian FY: April 1 to March 31. A date in Jan-Mar belongs to the
    FY that started the previous April."""

    if date.month >= FY_START_MONTH:
        return f"FY{date.year}-{str(date.year + 1)[2:]}"
    else:
        return f"FY{date.year - 1}-{str(date.year)[2:]}"


def classify_holding_period(entry_date, exit_date):
    """STCG if held <= LTCG_HOLDING_PERIOD_DAYS days, else LTCG. Exactly
    365 days is still STCG - only 366+ days qualifies as long-term,
    matching "more than 12 months" precisely, not "12 months or more"."""

    holding_days = (exit_date - entry_date).days
    return "LTCG" if holding_days > LTCG_HOLDING_PERIOD_DAYS else "STCG", holding_days


def load_all_closed_tranches():
    """
    Every real, closed tranche - full exits from trade_journal, plus
    partial exits from trade_journal_exits (joined back to their
    parent trade_journal row for the real entry_date).
    """

    conn = sqlite3.connect(DB_PATH)

    full_exits = pd.read_sql("""
        SELECT ticker, entry_date, exit_date, exit_shares, realized_pnl
        FROM trade_journal
        WHERE status = 'CLOSED' AND exit_date IS NOT NULL
    """, conn)

    partial_exits = pd.read_sql("""
        SELECT tj.ticker, tj.entry_date, tje.exit_date, tje.exit_shares, tje.realized_pnl
        FROM trade_journal_exits tje
        JOIN trade_journal tj ON tje.journal_id = tj.id
    """, conn)

    conn.close()

    all_tranches = pd.concat([full_exits, partial_exits], ignore_index=True)
    all_tranches = all_tranches.dropna(subset=["entry_date", "exit_date", "realized_pnl"])

    return all_tranches


def build_tax_report():

    tranches = load_all_closed_tranches()

    if tranches.empty:
        return None

    tranches["entry_date"] = pd.to_datetime(tranches["entry_date"])
    tranches["exit_date"] = pd.to_datetime(tranches["exit_date"])

    classifications = []
    holding_days_list = []
    fy_list = []

    for _, row in tranches.iterrows():
        classification, holding_days = classify_holding_period(row["entry_date"], row["exit_date"])
        classifications.append(classification)
        holding_days_list.append(holding_days)
        fy_list.append(get_financial_year(row["exit_date"]))

    tranches["classification"] = classifications
    tranches["holding_days"] = holding_days_list
    tranches["financial_year"] = fy_list

    report_rows = []

    for fy in sorted(tranches["financial_year"].unique()):

        fy_data = tranches[tranches["financial_year"] == fy]

        stcg_gains = fy_data[fy_data["classification"] == "STCG"]["realized_pnl"].sum()
        ltcg_gains = fy_data[fy_data["classification"] == "LTCG"]["realized_pnl"].sum()

        # LTCG exemption only applies against a genuine positive net
        # LTCG for the year - never against a loss, never carried
        # across financial years.
        taxable_ltcg = max(0, ltcg_gains - LTCG_ANNUAL_EXEMPTION_RS) if ltcg_gains > 0 else 0
        taxable_stcg = max(0, stcg_gains) if stcg_gains > 0 else 0

        stcg_tax = taxable_stcg * (STCG_RATE_PCT / 100)
        ltcg_tax = taxable_ltcg * (LTCG_RATE_PCT / 100)
        total_tax_before_cess = stcg_tax + ltcg_tax
        cess = total_tax_before_cess * (CESS_RATE_PCT / 100)
        estimated_total_tax = total_tax_before_cess + cess

        report_rows.append({
            "financial_year": fy,
            "stcg_gain_loss": round(stcg_gains, 2),
            "ltcg_gain_loss": round(ltcg_gains, 2),
            "ltcg_exemption_used": round(min(max(ltcg_gains, 0), LTCG_ANNUAL_EXEMPTION_RS), 2),
            "taxable_stcg": round(taxable_stcg, 2),
            "taxable_ltcg": round(taxable_ltcg, 2),
            "estimated_stcg_tax": round(stcg_tax, 2),
            "estimated_ltcg_tax": round(ltcg_tax, 2),
            "estimated_cess": round(cess, 2),
            "estimated_total_tax": round(estimated_total_tax, 2),
            "trade_count": len(fy_data),
        })

    return pd.DataFrame(report_rows), tranches


def run():

    print()
    print("=" * 70)
    print("TAX REPORT - ESTIMATE ONLY, NOT A FILING")
    print("=" * 70)
    print(f"Tax config version {CONFIG_VERSION}, last verified {CONFIG_LAST_VERIFIED}.")
    print("Verify current rates with a CA or incometaxindia.gov.in before filing.")
    print()

    result = build_tax_report()

    if result is None:
        print("[-] No real, closed trades found in trade_journal/trade_journal_exits.")
        return

    report_df, tranches = result

    print("[+] Summary by financial year:")
    print(report_df.to_string(index=False))

    print(f"\n[+] {len(tranches)} total closed tranches classified.")
    print(f"    STCG tranches: {(tranches['classification'] == 'STCG').sum()}")
    print(f"    LTCG tranches: {(tranches['classification'] == 'LTCG').sum()}")

    print("=" * 70)


if __name__ == "__main__":
    run()