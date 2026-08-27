import os


# ============================================================
# 1. execution_report.py
# ============================================================

exec_report_code = '''from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExecutionReport:
    order_id: str
    symbol: str
    requested_quantity: float
    filled_quantity: float
    avg_fill_price: float
    slippage_bps: float
    execution_timestamp: datetime
'''


# ============================================================
# 2. signal_validation.py
# ============================================================

signal_val_code = '''from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class SignalValidationResult:
    signal_id: str
    verdict: str  # PASS | CONDITIONAL | FAIL

    oos_sharpe: float
    deflated_sharpe: float
    p_value: float

    capacity_limit: float
    allowed_regimes: List[str]

    validation_timestamp: datetime
'''


# ============================================================
# 3. risk_constraints.py
# ============================================================

risk_const_code = '''from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConstraints:
    max_position_size: float
    max_sector_exposure: float
    max_drawdown: float
    volatility_target: float
'''


# ============================================================
# 4. contracts/manifest.py
# ============================================================

manifest_code = '''DOMAIN_NAME = "contracts"

VERSION = "1.0"

PUBLIC_API = {
    "ContractBase": "base.ContractBase",
    "ExecutionReport": "execution_report.ExecutionReport",
    "SignalValidationResult": "signal_validation.SignalValidationResult",
    "RiskConstraints": "risk_constraints.RiskConstraints"
}

FORBIDDEN_IMPORTS = []
'''


# ============================================================
# Write files
# ============================================================

contracts_dir = "contracts"

os.makedirs(contracts_dir, exist_ok=True)


files = {
    "execution_report.py": exec_report_code,
    "signal_validation.py": signal_val_code,
    "risk_constraints.py": risk_const_code,
    "manifest.py": manifest_code,
}


for filename, content in files.items():
    filepath = os.path.join(contracts_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Created: contracts/{filename}")


print()
print("=" * 60)
print("Institutional contracts initialized successfully.")
print("=" * 60)
print()
print("Created contracts:")
print("  - ExecutionReport")
print("  - SignalValidationResult")
print("  - RiskConstraints")
print()
print("Updated:")
print("  - contracts/manifest.py")
