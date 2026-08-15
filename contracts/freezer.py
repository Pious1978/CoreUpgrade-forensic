"""
Freezer

Provides deep recursive immutability mapping for dictionaries, lists, and sets 
across all domain payloads and audit structures.
"""

from types import MappingProxyType
from typing import Any


def freeze_metadata(value: Any) -> Any:
    """
    Recursively freezes nested dictionaries, lists, and sets into 
    MappingProxyType, tuples, and frozensets to guarantee platform-wide immutability.
    """
    if isinstance(value, dict):
        return MappingProxyType({k: freeze_metadata(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(freeze_metadata(v) for v in value)
    if isinstance(value, set):
        return frozenset(freeze_metadata(v) for v in value)
    return value
