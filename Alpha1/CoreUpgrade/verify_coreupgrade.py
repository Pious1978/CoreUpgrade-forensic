import os
import sys

# Auto-detect target directory: check if 'coreupgrade' subfolder exists, 
# or if we are already inside it (i.e. 'promotion' folder is right here)
if os.path.isdir("coreupgrade"):
    TARGET_DIR = "coreupgrade"
elif os.path.isdir("promotion"):
    TARGET_DIR = "."
else:
    TARGET_DIR = None

if not TARGET_DIR:
    print("❌ Error: Could not find 'coreupgrade' directory or 'promotion' folder in the current path.")
    print(f"Current working directory: {os.getcwd()}")
    sys.exit(1)

print("==================================================")
print(f" Verifying Structure & Flow relative to: '{os.path.abspath(TARGET_DIR)}'")
print("==================================================")

expected_items = [
    "promotion",
    "promotion/__init__.py",
    "promotion/exceptions.py",
    "promotion/status.py",
    "promotion/metadata.py",
    "promotion/trace.py",
    "promotion/context.py",
    "promotion/result.py",
    "promotion/events.py",
    "promotion/abstractions.py",
    "promotion/graph.py",
    "promotion/graph_validator.py",
    "promotion/factory.py",
    "promotion/middleware.py",
    "promotion/capability_registry.py",
    "promotion/policy_resolver.py",
    "promotion/migration.py",
    "promotion/feature_flags.py",
    "promotion/compensation.py",
    "promotion/configuration.py",
    "promotion/plugin_loader.py",
    "promotion/retry.py",
    "promotion/lock.py",
    "promotion/dlq.py",
    "promotion/health.py",
    "promotion/base_promoter.py",
    "promotion/engine.py",
    "promotion/bootstrap.py",
    "promotion/policies",
    "promotion/policies/base_policy.py",
    "promotion/policies/research_policy.py",
    "promotion/guards",
    "promotion/guards/capability_guard.py",
    "promotion/guards/lineage_dag_guard.py",
    "promotion/implementations",
    "promotion/implementations/research_to_portfolio.py"
]

missing_count = 0

for item in expected_items:
    full_path = item if TARGET_DIR == "." else os.path.join(TARGET_DIR, item)
    
    if os.path.exists(full_path):
        if os.path.isdir(full_path):
            print(f"  📁 [DIR OK]  {full_path}")
        else:
            print(f"  📄 [FILE OK] {full_path}")
    else:
        print(f"  ❌ [MISSING] {full_path}")
        missing_count += 1

print("==================================================")
if missing_count == 0:
    print("🎉 Success: All structural files and directories are present!")
    sys.exit(0)
else:
    print(f"⚠️ Failure: {missing_count} required item(s) are missing.")
    sys.exit(1)
