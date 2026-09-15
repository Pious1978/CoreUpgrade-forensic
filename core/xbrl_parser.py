"""
core/xbrl_parser.py

Addresses the foundation of #73 - bank-specific fundamentals (NIM,
GNPA/NNPA, capital adequacy) via NSE's official, regulator-mandated
XBRL filings, rather than yfinance's generic .info fields (confirmed
absent) or unofficial, undocumented third-party APIs (confirmed
fragile and ToS-risky).

HONEST, DIRECT STATEMENT OF WHAT'S VERIFIED AND WHAT ISN'T:

VERIFIED, by directly fetching and reading a real, live NSE XBRL
filing (KSB Limited's Integrated Filing - Financial, Q3 FY2025-26):
- The real, live URL pattern: nsearchives.nseindia.com/corporate/xbrl/...
- The real structure: well-formed XML, namespaced tags (e.g.
  "in-capmkt:RevenueFromOperations"), each value tied to a period via
  contextRef, with unitRef for currency/per-share values.
- The real taxonomy body (in.xbrl.org) confirms a dedicated "Banking
  taxonomy" extension exists, adding ~1,200 bank-specific elements to
  this same core schema - officially, structurally supporting exactly
  the kind of tagged, machine-readable NIM/GNPA/NNPA/CAR data #73 needs.

NOT YET VERIFIED - genuinely, directly stated, not glossed over:
- The EXACT tag names the banking taxonomy extension uses for NIM,
  GNPA, NNPA, and CAR specifically. NSE's own filing portal is a
  dynamic, JavaScript-rendered system that isn't reachable through
  search or a plain page fetch - actually confirming these requires
  either downloading one real bank's live XBRL filing directly (from
  NSE's site, logged in as a normal user, since the portal renders the
  real download links client-side) or receiving one such file to
  inspect. BANK_METRIC_TAGS below is a reasonable, evidence-informed
  starting guess based on the real, confirmed core-taxonomy naming
  convention (long, descriptive CamelCase) - explicitly NOT confirmed
  against a real bank filing yet, and should not be trusted as correct
  until checked against one.
"""

import xml.etree.ElementTree as ET
import re


# Real, confirmed XBRL namespace from the live NSE filing this was
# built and tested against.
NAMESPACES = {
    "xbrli": "http://www.xbrl.org/2003/instance",
    "in-capmkt": "http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt",
}

# HONEST, UNVERIFIED best-guess mapping - see the module docstring.
# Each entry lists multiple plausible real tag name candidates, since
# the exact one hasn't been confirmed - the parser tries each in turn.
BANK_METRIC_TAG_CANDIDATES = {
    "gross_npa_ratio": [
        "GrossNPARatio", "GrossNonPerformingAssetsRatio", "PercentageOfGrossNPAsToGrossAdvances",
    ],
    "net_npa_ratio": [
        "NetNPARatio", "NetNonPerformingAssetsRatio", "PercentageOfNetNPAsToNetAdvances",
    ],
    "net_interest_margin": [
        "NetInterestMargin", "NIM",
    ],
    "capital_adequacy_ratio": [
        "CapitalAdequacyRatio", "CRAR", "CapitalToRiskWeightedAssetsRatio",
    ],
}


def parse_xbrl_instance(xml_content):
    """
    Real, direct, tested parser for an NSE/SEBI XBRL instance document.
    Verified against the actual, real structure of a live filing -
    extracts every tagged value in the in-capmkt namespace (or any
    company-specific extension namespace sharing the same document)
    into a flat dict of {tag_name: [(value, context_ref), ...]}, since
    a single tag can legitimately appear multiple times under
    different contexts (e.g. current quarter vs year-to-date).
    """

    root = ET.fromstring(xml_content)

    # Real, direct handling: a company's own filing may declare
    # additional, bank-specific namespaces beyond the core "in-capmkt"
    # this was built against - collect every namespace actually
    # declared on the root element, not just the one confirmed above,
    # so tags from a bank-specific extension aren't silently missed.
    declared_namespaces = dict(re.findall(r'xmlns:(\w[\w-]*)="([^"]+)"', xml_content))

    results = {}

    for elem in root.iter():
        if "}" not in elem.tag:
            continue

        namespace_uri, tag_name = elem.tag[1:].split("}", 1)

        # Only real, substantive data tags - skip the xbrli: structural
        # elements (context, unit, entity) which aren't the actual
        # reported values.
        if namespace_uri == NAMESPACES["xbrli"]:
            continue

        context_ref = elem.get("contextRef")
        value = elem.text

        if value is None:
            continue

        results.setdefault(tag_name, []).append((value.strip(), context_ref))

    return results


def extract_bank_metric(parsed_tags, metric_key, context_ref=None):
    """
    Real, direct lookup of a specific bank metric from an already-
    parsed XBRL document, trying each candidate tag name in turn since
    the exact real name isn't yet confirmed (see module docstring).
    Returns None, with no invented fallback value, if none of the
    candidates are found - an honest "we don't know" rather than a
    fabricated number.
    """

    candidates = BANK_METRIC_TAG_CANDIDATES.get(metric_key, [])

    for tag_name in candidates:
        if tag_name in parsed_tags:
            matches = parsed_tags[tag_name]
            if context_ref:
                matches = [(v, c) for v, c in matches if c == context_ref]
            if matches:
                try:
                    return float(matches[0][0])
                except ValueError:
                    return matches[0][0]

    return None


def list_all_tags(parsed_tags):
    """
    Real, direct diagnostic: prints every tag name actually found in a
    parsed filing - the genuine way to confirm the real bank-metric
    tag names once a real bank XBRL file is available, rather than
    continuing to guess.
    """

    for tag_name in sorted(parsed_tags.keys()):
        print(tag_name)