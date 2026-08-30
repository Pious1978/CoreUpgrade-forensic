import os
import filecmp

DUPLICATES = ["Risk_Positioning_Audit.py", "Market_Data_Cache.py", "Schema_Migrator.py"]

for f in DUPLICATES:
    root_path = f
    scrap_path = os.path.join("Scrap", f)

    if not os.path.exists(root_path):
        print(f"[OK] {f} - not at root, nothing to fix")
        continue

    if not os.path.exists(scrap_path):
        print(f"[!] {f} - at root but NOT in Scrap - moving now")
        os.rename(root_path, scrap_path)
        continue

    if filecmp.cmp(root_path, scrap_path, shallow=False):
        os.remove(root_path)
        print(f"[+] {f} - confirmed identical to Scrap copy, removed stale root copy")
    else:
        print(f"[!] {f} - DIFFERENT content between root and Scrap - NOT removing, needs manual review")
