"""
Contract Registry (Strict Idempotent Freeze Guard)
"""

from typing import Type, Dict, Tuple, Optional, List
from threading import RLock
from packaging.version import Version, InvalidVersion
from contracts.base_contract import BaseContract
from contracts.exceptions import ContractRegistryError


class ContractRegistry:
    _lock = RLock()
    _frozen = False
    _versioned_registry: Dict[Tuple[str, str, str], Type[BaseContract]] = {}
    _version_order: Dict[Tuple[str, str], List[str]] = {}

    @classmethod
    def is_frozen(cls) -> bool:
        with cls._lock:
            return cls._frozen

    @classmethod
    def freeze(cls) -> None:
        with cls._lock:
            cls._frozen = True

    @classmethod
    def register(cls, domain: str, schema_name: str, schema_version: str, contract_cls: Type[BaseContract]) -> None:
        with cls._lock:
            version_key = (domain, schema_name, schema_version)
            
            if cls._frozen:
                if version_key in cls._versioned_registry:
                    existing_cls = cls._versioned_registry[version_key]
                    if existing_cls == contract_cls:
                        return  # Idempotent match during warm reboots or test reloads
                    raise ContractRegistryError(
                        f"Registry frozen with conflicting registration for {version_key}: "
                        f"existing '{existing_cls.__name__}' vs new '{contract_cls.__name__}'."
                    )
                raise ContractRegistryError(f"Registry is frozen. Cannot register new schema version {version_key}.")

            if not isinstance(contract_cls, type) or not issubclass(contract_cls, BaseContract):
                raise ContractRegistryError("Validation failed: Registered class must inherit from BaseContract.")

            try:
                Version(schema_version)
            except InvalidVersion as e:
                raise ContractRegistryError(f"Invalid semantic version string '{schema_version}': {e}") from e

            expected_domain = getattr(contract_cls, "DOMAIN", None)
            expected_schema = getattr(contract_cls, "SCHEMA_NAME", None)

            if expected_domain and expected_domain != domain:
                raise ContractRegistryError(f"Domain mismatch: class declares DOMAIN='{expected_domain}', but registered under '{domain}'.")
            if expected_schema and expected_schema != schema_name:
                raise ContractRegistryError(f"Schema mismatch: class declares SCHEMA_NAME='{expected_schema}', but registered under '{schema_name}'.")

            if version_key in cls._versioned_registry:
                raise ContractRegistryError(f"Contract for domain '{domain}', schema '{schema_name}' v{schema_version} is already registered.")
            
            cls._versioned_registry[version_key] = contract_cls
            
            order_key = (domain, schema_name)
            if order_key not in cls._version_order:
                cls._version_order[order_key] = []
            cls._version_order[order_key].append(schema_version)

    @classmethod
    def get(cls, domain: str, schema_name: str, schema_version: Optional[str] = None) -> Type[BaseContract]:
        with cls._lock:
            if schema_version:
                version_key = (domain, schema_name, schema_version)
                if version_key not in cls._versioned_registry:
                    raise ContractRegistryError(f"No contract registered for {version_key}.")
                return cls._versioned_registry[version_key]

            order_key = (domain, schema_name)
            if order_key not in cls._version_order or not cls._version_order[order_key]:
                raise ContractRegistryError(f"No contract registered for domain '{domain}', schema '{schema_name}'.")

            latest_version = max(cls._version_order[order_key], key=Version)
            return cls._versioned_registry[(domain, schema_name, latest_version)]

    @classmethod
    def get_latest(cls, domain: str, schema_name: str) -> Type[BaseContract]:
        return cls.get(domain, schema_name, schema_version=None)
