"""
core/tax_config.py

#57 - Tax law / configuration, deliberately kept separate from trade
facts and calculations (Tax_Report.py). Tax law changes; trade history
doesn't. Keeping these separate means an annual budget change only
ever requires editing this one file.

RATES CONFIRMED via web search, multiple consistent sources, as of
September 2026 (Budget 2026 made no changes to these rates for FY
2026-27, per Union Budget coverage and CA-authored guides):

- STCG (Section 111A): listed equity, held <= 12 months, STT paid -
  flat 20%
- LTCG (Section 112A): listed equity, held > 12 months - 12.5% on
  gains exceeding the annual exemption
- LTCG annual exemption: Rs 1,25,000 per financial year
- Health & Education Cess: 4% on the tax amount (not on the gain)
- Surcharge: applies above certain income thresholds - NOT modeled
  here, since it depends on total income beyond just capital gains,
  which this tool doesn't have visibility into

IMPORTANT: tax law changes, sometimes annually via Union Budget
announcements. Verify these figures against the Income Tax Department
(incometaxindia.gov.in) or a Chartered Accountant before relying on
this for actual tax filing. This tool estimates; it does not file.
"""

CONFIG_VERSION = "1.0"
CONFIG_LAST_VERIFIED = "2026-09-01"
CONFIG_SOURCE_NOTE = ("Multiple consistent sources confirm Budget 2026 made no "
                       "changes to equity capital gains rates for FY 2026-27.")

LTCG_HOLDING_PERIOD_DAYS = 365  # "more than 12 months" - exactly 365 days is
                                  # still STCG, only 366+ days qualifies as LTCG

STCG_RATE_PCT = 20.0
LTCG_RATE_PCT = 12.5
LTCG_ANNUAL_EXEMPTION_RS = 125000

CESS_RATE_PCT = 4.0  # applied on the tax amount itself, not on the gain

# Indian financial year: April 1 to March 31
FY_START_MONTH = 4