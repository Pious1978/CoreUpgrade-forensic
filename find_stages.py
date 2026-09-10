with open("pipeline_log.txt", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "STARTING STAGE" in line:
        for j in range(i+1, min(i+4, len(lines))):
            candidate = lines[j].strip()
            if candidate.endswith(".py") or "factor_registry" in candidate:
                print(f"Stage: {candidate}")
                break
