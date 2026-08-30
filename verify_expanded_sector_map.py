import sys
sys.path.insert(0, ".")
from core.sector_map import UNIVERSE, get_sector

print(f"Total entries: {len(UNIVERSE)}")
print()
print("=== spot check real, well-known stocks ===")
for tk in ["RELIANCE", "TCS", "HDFCBANK", "SBIN", "MARUTI", "SUNPHARMA", "HINDUNILVR", "TATASTEEL", "DLF"]:
    print(f"{tk}: {get_sector(tk)}")

print()
print("=== sector distribution ===")
from collections import Counter
sectors = Counter(v["sector"] for v in UNIVERSE.values())
for sector, count in sectors.most_common():
    print(f"  {sector}: {count}")
