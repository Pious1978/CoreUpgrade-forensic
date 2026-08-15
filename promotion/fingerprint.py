from dataclasses import dataclass, asdict, is_dataclass
import hashlib
import json
from typing import Any

def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [canonicalize(x) for x in value]
    if isinstance(value, tuple):
        return [canonicalize(x) for x in value]
    return value

@dataclass(frozen=True)
class ContractFingerprint:
    contract_id: str
    version: int
    sha256: str

    @staticmethod
    def calculate(contract: Any) -> "ContractFingerprint":
        contract_id = getattr(contract, "immutable_id", getattr(contract, "id", "unknown"))
        version = getattr(contract, "version", 1)
        if is_dataclass(contract):
            raw_dict = asdict(contract)
        else:
            raw_dict = contract.__dict__ if hasattr(contract, "__dict__") else dict(contract)
        canonical_data = canonicalize(raw_dict)
        data_str = json.dumps(canonical_data, sort_keys=True, default=str)
        digest = hashlib.sha256(data_str.encode("utf-8")).hexdigest()
        return ContractFingerprint(contract_id=str(contract_id), version=int(version), sha256=digest)
