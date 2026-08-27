import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Tuple

from event_store.exceptions import (
    EventIntegrityError,
    UnsupportedSchemaVersion,
    UnknownEventType,
    EventDeserializationError
)
from event_store.schema_registry import EventSchemaRegistry
from oms.events.base import BaseOrderEvent
from event_store.serializers.type_converter import TypeConverter


@dataclass(frozen=True, slots=True)
class SerializedEvent:
    """Immutable transport container for serialized event data."""
    event_type: str
    schema_version: int
    payload: str
    payload_hash: str
    hash_algorithm: str = "SHA256"


class EventSerializer:
    """Infrastructure-agnostic serialization boundary with cryptographic integrity."""

    @staticmethod
    def serialize(event: BaseOrderEvent) -> SerializedEvent:
        event_type = event.__class__.__name__
        schema_version = getattr(event.__class__, "SCHEMA_VERSION", 1)

        raw_dict = TypeConverter.to_json_primitive(event)
        
        payload = json.dumps(raw_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()

        return SerializedEvent(
            event_type=event_type,
            schema_version=schema_version,
            payload=payload,
            payload_hash=payload_hash,
            hash_algorithm="SHA256"
        )

    @staticmethod
    def deserialize(serialized: SerializedEvent) -> BaseOrderEvent:
        if not serialized.payload_hash:
            raise EventIntegrityError(f"Missing payload hash for {serialized.event_type}.")

        if serialized.hash_algorithm != "SHA256":
            raise EventIntegrityError(f"Unsupported hash algorithm: {serialized.hash_algorithm}")

        # 1. Cryptographic Integrity Verification
        computed_hash = hashlib.sha256(serialized.payload.encode('utf-8')).hexdigest()
        if not hmac.compare_digest(computed_hash, serialized.payload_hash):
            raise EventIntegrityError(
                f"Integrity check failed for {serialized.event_type}. "
                f"Payload has been tampered with or corrupted."
            )

        # 2. Consolidated Registry Lookup
        try:
            event_class = EventSchemaRegistry.get_event_class(serialized.event_type)
            target_version = EventSchemaRegistry.get_target_version(serialized.event_type)
        except ValueError as e:
            raise UnknownEventType(str(e))
        
        # 3. Future Schema Protection
        if serialized.schema_version > target_version:
            raise UnsupportedSchemaVersion(
                f"Event {serialized.event_type} is schema version {serialized.schema_version}, "
                f"but system only understands up to version {target_version}."
            )
            
        # 4. JSON Parsing Safety
        try:
            raw_dict = json.loads(serialized.payload)
        except json.JSONDecodeError as e:
            raise EventIntegrityError(f"Malformed JSON for {serialized.event_type}.") from e

        # 5. Chained Upcast
        if serialized.schema_version < target_version:
            raw_dict = EventSchemaRegistry.upcast(
                serialized.event_type, 
                serialized.schema_version, 
                raw_dict, 
                target_version
            )

        # 6. Domain Reconstruction Safety
        try:
            return TypeConverter.from_json_primitive(event_class, raw_dict)
        except Exception as e:
            raise EventDeserializationError(f"Failed to reconstruct {serialized.event_type}.") from e
