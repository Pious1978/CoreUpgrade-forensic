import os

target_file = os.path.join("portfolio", "rebalancing", "rebalance_orchestrator.py")

if os.path.exists(target_file):
    with open(target_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    with open(target_file, "w", encoding="utf-8") as f:
        for line in lines:
            # Strip out the forbidden execution imports
            if "from execution" not in line and "import execution" not in line:
                f.write(line)
    print("Successfully decoupled portfolio from execution.")
else:
    print(f"Could not find {target_file}. You may need to remove the imports manually.")
