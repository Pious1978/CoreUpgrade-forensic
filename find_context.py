with open("pipeline_log.txt", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "possibly delisted" in line:
        print(f"First possibly-delisted error is at line {i}")
        print("Context (10 lines before):")
        for j in range(max(0, i-10), i):
            print(f"  {j}: {lines[j].rstrip()}")
        break

print()
print("All RelativeStrengthEngine mentions:")
for i, line in enumerate(lines):
    if "RelativeStrengthEngine" in line:
        print(f"  {i}: {line.rstrip()}")

print()
print("First 15 lines after each RelativeStrengthEngine stage start:")
for i, line in enumerate(lines):
    if "RelativeStrengthEngine.py" in line:
        for j in range(i, min(i+15, len(lines))):
            print(f"  {j}: {lines[j].rstrip()}")
        print("  ---")
