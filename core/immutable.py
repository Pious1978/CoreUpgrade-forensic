from types import MappingProxyType
from typing import Mapping, Any, Sequence, Tuple


def freeze_value(value: Any) -> Any:
    """Recursively freezes dictionaries, lists, tuples, and sets with string-normalized keys."""
    if isinstance(value, MappingProxyType):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(k): freeze_value(v)
            for k, v in value.items()
        })
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(v) for v in value)
    if isinstance(value, set):
        return frozenset(freeze_value(v) for v in value)
    return value


def freeze_mapping(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Wraps a mapping structure in a deep read-only proxy with normalized keys."""
    return freeze_value(data)


def freeze_findings(items: Sequence[Mapping[str, Any]]) -> Tuple[Mapping[str, Any], ...]:
    """Recursively freezes an institutional findings sequence."""
    return tuple(freeze_mapping(item) for item in items)
