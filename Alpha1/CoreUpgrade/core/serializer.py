from types import MappingProxyType
from typing import Any, Mapping
from dataclasses import is_dataclass, asdict


def make_serializable(obj: Any) -> Any:
    """
    Recursively transforms MappingProxyType, tuples, dataclasses,
    and collections into standard JSON-serializable structures.
    """
    if isinstance(obj, Mapping):
        return {str(k): make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [make_serializable(x) for x in obj]
    if is_dataclass(obj):
        return make_serializable(asdict(obj))
    return obj
