class EventStoreError(Exception):
    """Base class for all event store and serialization failures."""
    pass


class EventIntegrityError(EventStoreError):
    """Stored payload failed cryptographic integrity verification."""
    pass


class UnsupportedSchemaVersion(EventStoreError):
    """Stored event uses a newer schema than this binary supports."""
    pass


class UnknownEventType(EventStoreError):
    """Event type is not registered in the schema registry."""
    pass


class EventDeserializationError(EventStoreError):
    """Event payload could not be mathematically reconstructed."""
    pass


class StreamConcurrencyError(EventStoreError):
    """Raised when the expected stream version does not match reality."""
    pass


class EventStoreIntegrityError(EventStoreError):
    """Raised when batch sizes or stream logic invariants are violated."""
    pass
