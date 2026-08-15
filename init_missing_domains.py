import os

# 1. Setup Research
os.makedirs("research", exist_ok=True)
with open("research/engine.py", "w", encoding="utf-8") as f:
    f.write("def generate_candidates():\n    return []\n\ndef backtest():\n    return {}\n")
    
with open("research/manifest.py", "w", encoding="utf-8") as f:
    f.write('DOMAIN_NAME = "research"\n')
    f.write('VERSION = "1.0"\n')
    f.write('PUBLIC_API = {"generate_candidates": "engine.generate_candidates", "backtest": "engine.backtest"}\n')
    f.write('FORBIDDEN_IMPORTS = ["execution"]\n')

# 2. Setup Infrastructure
os.makedirs("infrastructure", exist_ok=True)
with open("infrastructure/market_data.py", "w", encoding="utf-8") as f:
    f.write("def fetch_market_data():\n    return {}\n")
    
with open("infrastructure/manifest.py", "w", encoding="utf-8") as f:
    f.write('DOMAIN_NAME = "infrastructure"\n')
    f.write('VERSION = "1.0"\n')
    f.write('PUBLIC_API = {"fetch_market_data": "market_data.fetch_market_data"}\n')
    f.write('FORBIDDEN_IMPORTS = []\n')

print("Created engine modules and updated manifests for research and infrastructure.")
