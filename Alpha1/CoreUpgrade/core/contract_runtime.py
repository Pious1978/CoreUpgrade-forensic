"""Core infrastructure for processing contracts. No business schemas here."""
class ContractBase: pass
class ContractValidationError(Exception): pass
\n# --- Merged from contracts\base.py ---\nimport json
import hashlib
from dataclasses import fields
from datetime import datetime
from typing import Dict, Any, Tuple, List
from abc import ABC, abstractmethod
from .exceptions import ContractValidationError

class ContractBase(ABC):
    """
    Abstract base for all domain contracts. Decoupled from dataclass field inheritance
    to prevent schema ordering collisions, incorporating canonical serialization and fingerprinting.
    """
    schema_version: str = "1.0"

    def __post_init__(self):
        self.ensure_valid()

    @abstractmethod
    def validate(self) -> Tuple[bool, List[str]]:
        """Must be implemented by concrete contract subclasses."""
        pass

    def ensure_valid(self):
        valid, errors = self.validate()
        if not valid:
            raise ContractValidationError(self.__class__.__name__, errors)
        return self

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for field in fields(self):
            value = getattr(self, field.name)
            result[field.name] = self._serialize(value)
        result["schema_version"] = getattr(self, "schema_version", "1.0")
        return result

    @staticmethod
    def _serialize(value):
        if isinstance(value, float):
            # Canonical float normalization to prevent floating-point drift (e.g. 0.3000000004 vs 0.3)
            return round(value, 8)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, tuple):
            return [ContractBase._serialize(v) for v in value]
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if isinstance(value, dict):
            return {k: ContractBase._serialize(v) for k, v in value.items()}
        return value

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        clean_data = {k: v for k, v in data.items() if k != "schema_version"}
        return cls(**clean_data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str):
        return cls.from_dict(json.loads(json_str))

    def fingerprint(self) -> str:
        payload = {
            "schema_version": getattr(self, "schema_version", "1.0"),
            "contract_type": self.__class__.__name__,
            "payload": self.to_dict()
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
