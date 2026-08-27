"""
Crypto Utilities

Centralized source of truth for cryptographic hashing algorithms (HashAlgorithm Enum), 
frozen excluded field sets, and canonical payload hashing.
"""

from enum import Enum
import hashlib
import json
from typing import Dict, Callable, Any, FrozenSet
from contracts.exceptions import ContractIntegrityError
from contracts.canonical import to_canonical_dict, CANONICAL_EXCLUDED_FIELDS


class HashAlgorithm(str, Enum):
    SHA256 = "sha256"
    SHA512 = "sha512"


HASHERS: Dict[HashAlgorithm, Callable[[bytes], Any]] = {
    HashAlgorithm.SHA256: hashlib.sha256,
    HashAlgorithm.SHA512: hashlib.sha512,
}

DEFAULT_HASH_ALGORITHM = HashAlgorithm.SHA256


def compute_canonical_hash(
    contract: Any,
    hash_algorithm: HashAlgorithm = DEFAULT_HASH_ALGORITHM,
) -> str:
    """
    Computes a deterministic cryptographic digest of a contract instance 
    using canonical serialization, filtering out metadata exclusion fields.
    """
    payload = to_canonical_dict(contract)
    clean_payload = {k: v for k, v in payload.items() if k not in CANONICAL_EXCLUDED_FIELDS}

    canonical_json = json.dumps(
        clean_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    hasher_func = HASHERS.get(hash_algorithm)
    if not hasher_func:
        raise ContractIntegrityError(f"Unsupported hash algorithm: {hash_algorithm}")

    return hasher_func(canonical_json.encode("utf-8")).hexdigest()
