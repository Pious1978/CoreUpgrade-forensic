"""
Canonical Serializer & Environment Fingerprinter
"""

import dataclasses
import hashlib
import json
import platform
import sys
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict


class CanonicalSerializer:
    @staticmethod
    def _default_encoder(obj: Any) -> Any:
        # Explicit deterministic datetime/date/time handling.
        if isinstance(obj, datetime):
            return obj.isoformat()

        if isinstance(obj, date):
            return obj.isoformat()

        if isinstance(obj, time):
            return obj.isoformat()

        # Decimal must be represented deterministically.
        if isinstance(obj, Decimal):
            return str(obj)

        # Domain objects with an explicit canonical representation.
        if hasattr(obj, "to_dict") and callable(obj.to_dict):
            return obj.to_dict()

        # Dataclasses are converted structurally.
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)

        raise TypeError(
            f"Object of type {obj.__class__.__name__} "
            "is not canonically serializable."
        )

    @staticmethod
    def serialize(obj: Any) -> str:
        """
        Deterministically serializes data structures.

        Strictly excludes default=str to fail loudly on
        unhandled/non-deterministic types.
        """
        return json.dumps(
            obj,
            default=CanonicalSerializer._default_encoder,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def hash(obj: Any) -> str:
        if isinstance(obj, str):
            s = obj
        else:
            s = CanonicalSerializer.serialize(obj)

        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    @classmethod
    def digest(cls, obj: Any) -> str:
        """Internal helper combining serialization and hashing directly."""
        return cls.hash(cls.serialize(obj))

    @staticmethod
    def get_environment_fingerprint() -> Dict[str, str]:
        """Captures strict environment metadata for multi-month reproducibility."""
        return {
            "python_version": sys.version,
            "os": platform.platform(),
            "cpu_arch": platform.machine(),
            "serializer_version": "1.0.0",
        }