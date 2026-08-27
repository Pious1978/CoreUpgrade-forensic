"""
Contract Factory

Responsible for looking up schema definitions in the ContractRegistry, 
verifying raw cryptographic wire hashes, and instantiating verified contracts.
"""

import json
import hmac
from typing import Dict, Any
from contracts.base_contract import BaseContract
from contracts.registry import ContractRegistry
from contracts.crypto import HashAlgorithm, compute_canonical_hash
from contracts.serializer import ContractSerializer
from contracts.exceptions import ContractSerializationError, ContractIntegrityError


class ContractFactory:

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> BaseContract:
        """
        Extracts schema metadata, verifies cryptographic integrity on raw payload, 
        resolves the concrete class from the registry, and constructs the contract.
        """
        domain = data.get("domain")
        schema_name = data.get("schema_name")
        schema_version = data.get("schema_version")
        provided_hash = data.get("payload_hash")
        hash_algo = data.get("hash_algorithm", "sha256")

        if not domain or not schema_name:
            raise ContractSerializationError("Payload missing mandatory 'domain' or 'schema_name' property.")
        if not provided_hash:
            raise ContractIntegrityError("Payload missing mandatory 'payload_hash' property.")

        # Resolve contract class from registry
        contract_cls = ContractRegistry.get(domain, schema_name, schema_version)

        if not hasattr(contract_cls, "from_dict"):
            raise ContractSerializationError(f"Contract class '{contract_cls.__name__}' does not implement 'from_dict'.")

        # Instantiate concrete class; its internal post_init runs the strict ValidationPipeline
        contract = contract_cls.from_dict(data)
        return contract

    @staticmethod
    def from_json(payload_str: str) -> BaseContract:
        """Deserializes a JSON wire string into a verified concrete domain contract."""
        data = ContractSerializer.from_json(payload_str)
        return ContractFactory.from_dict(data)
