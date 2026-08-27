"""
Migration Registry (Namespaced & Thread-Safe)

Manages semantic schema migrations across domain boundaries under thread-safe lock protection.
"""

from typing import Dict, Callable, Any, Tuple
from threading import RLock
from contracts.exceptions import ContractRegistryError


class MigrationRegistry:
    _lock = RLock()
    _migrations: Dict[Tuple[str, str, str, str], Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    @classmethod
    def register(cls, domain: str, schema_name: str, from_version: str, to_version: str, migration_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Registers a namespaced migration function thread-safely."""
        with cls._lock:
            key = (domain, schema_name, from_version, to_version)
            cls._migrations[key] = migration_func

    @classmethod
    def migrate(cls, domain: str, schema_name: str, from_version: str, to_version: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a registered migration path for a specific domain and schema thread-safely."""
        with cls._lock:
            key = (domain, schema_name, from_version, to_version)
            if key not in cls._migrations:
                raise ContractRegistryError(f"No migration path registered for domain '{domain}', schema '{schema_name}' from v{from_version} to v{to_version}.")
            return cls._migrations[key](payload)
