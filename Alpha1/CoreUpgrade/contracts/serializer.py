"""
Contract Serializer (Transport Layer)

Handles raw JSON string encoding and decoding for wire transport, 
completely decoupled from schema registries and cryptographic hashing.
"""

import json
from typing import Dict, Any
from contracts.exceptions import ContractSerializationError


class ContractSerializer:

    @staticmethod
    def to_json(data: Dict[str, Any]) -> str:
        """Serializes a dictionary payload into a canonical JSON wire string."""
        try:
            return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except Exception as e:
            raise ContractSerializationError(f"Failed to encode JSON payload: {e}") from e

    @staticmethod
    def from_json(payload_str: str) -> Dict[str, Any]:
        """Parses a JSON wire string into a raw dictionary."""
        try:
            return json.loads(payload_str)
        except json.JSONDecodeError as e:
            raise ContractSerializationError(f"Failed to parse JSON string: {e}") from e
