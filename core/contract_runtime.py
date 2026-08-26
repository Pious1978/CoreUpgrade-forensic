import json
import hashlib
from dataclasses import fields, dataclass, asdict, is_dataclass
from typing import Any, Dict, Type, TypeVar, Optional, List, Tuple
from abc import ABC, abstractmethod
from .exceptions import ContractValidationError

T = TypeVar("T", bound="ContractBase")

@dataclass(frozen=True)
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
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        if not is_dataclass(cls):
            return cls(**data)
        
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        data = json.loads(json_str)
        return cls.from_dict(data)

    def fingerprint(self) -> str:
        json_data = self.to_json()
        return hashlib.sha256(json_data.encode("utf-8")).hexdigest()