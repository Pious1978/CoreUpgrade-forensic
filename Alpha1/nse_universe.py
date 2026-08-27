# ============================
# NSE UNIVERSE (SMART BUILDER)
# ============================

UNIVERSE = {
    # ================= ENERGY / PSU =================
    "RELIANCE.NS": {"sector": "Energy", "theme": "Energy + Digital Infra"},
    "ONGC.NS": {"sector": "Energy", "theme": "Oil PSU"},
    "IOC.NS": {"sector": "Energy", "theme": "Oil PSU"},
    "BPCL.NS": {"sector": "Energy", "theme": "Oil PSU"},
    "HPCL.NS": {"sector": "Energy", "theme": "Oil PSU"},
    "GAIL.NS": {"sector": "Energy", "theme": "Gas Utility"},
    "PETRONET.NS": {"sector": "Energy", "theme": "LNG Infra"},

    # ================= POWER =================
    "POWERGRID.NS": {"sector": "Energy", "theme": "Power Transmission"},
    "NTPC.NS": {"sector": "Energy", "theme": "Power Generation"},
    "TATAPOWER.NS": {"sector": "Energy", "theme": "Renewable + Utility"},
    "ADANIPOWER.NS": {"sector": "Energy", "theme": "Power Generation"},
    "NLCINDIA.NS": {"sector": "Energy", "theme": "Coal Power"},

    # ================= BANKING =================
    "HDFCBANK.NS": {"sector": "Banking", "theme": "Private Banking"},
    "ICICIBANK.NS": {"sector": "Banking", "theme": "Private Banking"},
    "SBIN.NS": {"sector": "Banking", "theme": "PSU Banking"},
    "AXISBANK.NS": {"sector": "Banking", "theme": "Private Banking"},
    "KOTAKBANK.NS": {"sector": "Banking", "theme": "Private Banking"},
    "INDUSINDBK.NS": {"sector": "Banking", "theme": "Mid Private Bank"},
    "BANKBARODA.NS": {"sector": "Banking", "theme": "PSU Banking"},
    "PNB.NS": {"sector": "Banking", "theme": "PSU Banking"},

    # ================= IT / AI =================
    "TCS.NS": {"sector": "IT", "theme": "AI Services"},
    "INFY.NS": {"sector": "IT", "theme": "Cloud + AI"},
    "HCLTECH.NS": {"sector": "IT", "theme": "Enterprise IT"},
    "WIPRO.NS": {"sector": "IT", "theme": "IT Services"},
    "TECHM.NS": {"sector": "IT", "theme": "Telecom + IT"},
    "PERSISTENT.NS": {"sector": "IT", "theme": "AI Engineering"},
    "LTIM.NS": {"sector": "IT", "theme": "Digital Transformation"},

    # ================= DEFENCE =================
    "HAL.NS": {"sector": "Defence", "theme": "Aerospace & Defence"},
    "BEL.NS": {"sector": "Defence", "theme": "Electronics Defence"},
    "MAZDOCK.NS": {"sector": "Defence", "theme": "Naval Shipbuilding"},
    "BDL.NS": {"sector": "Defence", "theme": "Missile Systems"},
    "COCHINSHIP.NS": {"sector": "Defence", "theme": "Shipbuilding"},
    "GRSE.NS": {"sector": "Defence", "theme": "Naval Defence"},

    # ================= INFRA =================
    "LT.NS": {"sector": "Infrastructure", "theme": "Infra + EPC"},
    "RVNL.NS": {"sector": "Infrastructure", "theme": "Rail Infra"},
    "IRFC.NS": {"sector": "Infrastructure", "theme": "Rail Financing"},
    "IRCON.NS": {"sector": "Infrastructure", "theme": "Rail EPC"},
    "NBCC.NS": {"sector": "Infrastructure", "theme": "Govt Infra"},
    "PNCINFRA.NS": {"sector": "Infrastructure", "theme": "Road EPC"},

    # ================= RAIL + LOGISTICS =================
    "CONCOR.NS": {"sector": "Logistics", "theme": "Rail Freight"},
    "ADANIPORTS.NS": {"sector": "Logistics", "theme": "Ports"},
    "DELHIVERY.NS": {"sector": "Logistics", "theme": "E-commerce Logistics"},
    "GATI.NS": {"sector": "Logistics", "theme": "Express Logistics"},

    # ================= ENERGY TRANSITION =================
    "ADANIGREEN.NS": {"sector": "Energy Transition", "theme": "Green Energy"},
    "SUZLON.NS": {"sector": "Energy Transition", "theme": "Wind Energy"},
    "INOXWIND.NS": {"sector": "Energy Transition", "theme": "Wind Infra"},

    # ================= CONSUMER =================
    "TITAN.NS": {"sector": "Consumer", "theme": "Jewellery"},
    "DMART.NS": {"sector": "Consumer", "theme": "Retail"},
    "ASIANPAINT.NS": {"sector": "Consumer", "theme": "Paints"},
    "NESTLEIND.NS": {"sector": "Consumer", "theme": "FMCG"},
    "HINDUNILVR.NS": {"sector": "Consumer", "theme": "FMCG"},
    "ITC.NS": {"sector": "Consumer", "theme": "FMCG + Cigarettes"},

    # ================= PHARMA =================
    "SUNPHARMA.NS": {"sector": "Healthcare", "theme": "Pharma"},
    "DRREDDY.NS": {"sector": "Healthcare", "theme": "Pharma"},
    "DIVISLAB.NS": {"sector": "Healthcare", "theme": "API Pharma"},
    "APOLLOHOSP.NS": {"sector": "Healthcare", "theme": "Hospitals"},
    "CIPLA.NS": {"sector": "Healthcare", "theme": "Pharma"},
    "LUPIN.NS": {"sector": "Healthcare", "theme": "Pharma"},

    # ================= FINTECH =================
    "PAYTM.NS": {"sector": "FinTech", "theme": "Digital Payments"},
    "POLICYBZR.NS": {"sector": "FinTech", "theme": "Insurance Tech"},
    "JIOFIN.NS": {"sector": "FinTech", "theme": "Financial Services"},
}

# ============================
# PUBLIC API
# ============================
def get_nse_universe():
    return UNIVERSE