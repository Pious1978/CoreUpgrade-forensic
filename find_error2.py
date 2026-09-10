with open("pipeline_log2.txt", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "RelativeStrengthEngine.py" in line:
        for j in range(i, min(i+20, len(lines))):
            print(f"  {j}: {lines[j].rstrip()}")
        print("  ---")
        break
