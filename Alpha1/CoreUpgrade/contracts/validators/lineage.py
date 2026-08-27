"""
Lineage Validators (Dedicated State and Trust History Engines)

Provides clear separation between BaseHistoryValidator, StateHistoryValidator, 
and TrustHistoryValidator, eliminating leaking abstractions.
"""

from typing import Tuple, Mapping, Any, FrozenSet
from datetime import datetime, timezone
from contracts.state import ContractState
from contracts.trust import TrustLevel
from contracts.state_machine import validate_transition
from contracts.trust_machine import validate_trust_transition
from contracts.exceptions import ContractValidationError

STATE_AUDIT_FIELDS: FrozenSet[str] = frozenset({"state", "timestamp", "actor", "reason"})
TRUST_AUDIT_FIELDS: FrozenSet[str] = frozenset({"from", "to", "timestamp", "actor", "reason"})

MAX_ACTOR_LENGTH = 128
MAX_REASON_LENGTH = 1024


def _parse_timestamp(ts_str: str) -> datetime:
    if not isinstance(ts_str, str) or not ts_str.strip():
        raise ContractValidationError("Timestamp must be a non-empty string.")
    try:
        cleaned = ts_str.strip()
        if cleaned.endswith(("Z", "z")):
            normalized = cleaned[:-1] + "+00:00"
        else:
            normalized = cleaned

        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            raise ContractValidationError(f"Timestamp validation failed: naive datetimes forbidden ('{ts_str}').")
        return dt.astimezone(timezone.utc)
    except Exception as e:
        if isinstance(e, ContractValidationError):
            raise e
        raise ContractValidationError(f"Invalid ISO timestamp format '{ts_str}': {e}") from e


class BaseHistoryValidator:
    def __init__(self, allowed_fields: FrozenSet[str], context: str):
        self.allowed_fields = allowed_fields
        self.context = context

    def validate_entry(self, entry: Any) -> None:
        if not isinstance(entry, Mapping):
            raise ContractValidationError(f"{self.context.capitalize()} history entry must implement Mapping.")

        keys = set(entry)
        if keys != self.allowed_fields:
            missing = self.allowed_fields - keys
            extra = keys - self.allowed_fields
            errors = []
            if missing:
                errors.append(f"missing={sorted(missing)}")
            if extra:
                errors.append(f"extra={sorted(extra)}")
            raise ContractValidationError(f"Invalid {self.context} history fields: " + ", ".join(errors))

        actor = entry["actor"]
        reason = entry["reason"]
        
        if not isinstance(actor, str) or not actor.strip():
            raise ContractValidationError(f"{self.context.capitalize()} history actor must be a non-empty string.")
        if len(actor) > MAX_ACTOR_LENGTH:
            raise ContractValidationError(f"{self.context.capitalize()} history actor exceeds max length of {MAX_ACTOR_LENGTH}.")

        if not isinstance(reason, str) or not reason.strip():
            raise ContractValidationError(f"{self.context.capitalize()} history reason must be a non-empty string.")
        if len(reason) > MAX_REASON_LENGTH:
            raise ContractValidationError(f"{self.context.capitalize()} history reason exceeds max length of {MAX_REASON_LENGTH}.")


class StateHistoryValidator(BaseHistoryValidator):
    def __init__(self):
        super().__init__(STATE_AUDIT_FIELDS, "state")

    def validate(self, history: Tuple[Mapping[str, Any], ...], current_state: ContractState) -> None:
        if not history:
            return

        first_entry = history[0]
        self.validate_entry(first_entry)

        if first_entry["state"] != ContractState.CREATED.value:
            raise ContractValidationError("State history must begin at CREATED state.")

        prev_time = _parse_timestamp(first_entry["timestamp"])
        current_s = ContractState(first_entry["state"])

        for entry in history[1:]:
            self.validate_entry(entry)

            curr_time = _parse_timestamp(entry["timestamp"])
            if curr_time <= prev_time:
                raise ContractValidationError("State history timestamps must be strictly monotonic (increasing).")
            prev_time = curr_time

            try:
                next_s = ContractState(entry["state"])
            except ValueError as e:
                raise ContractValidationError(f"Invalid state value in history: '{entry['state']}'") from e

            validate_transition(current_s, next_s)
            current_s = next_s

        if current_s != current_state:
            validate_transition(current_s, current_state)


class TrustHistoryValidator(BaseHistoryValidator):
    def __init__(self):
        super().__init__(TRUST_AUDIT_FIELDS, "trust")

    def validate(self, history: Tuple[Mapping[str, Any], ...], current_trust: TrustLevel) -> None:
        if not history:
            return

        first_entry = history[0]
        self.validate_entry(first_entry)

        if first_entry["from"] != TrustLevel.UNVERIFIED.value:
            raise ContractValidationError("Trust history must begin from UNVERIFIED trust level.")

        try:
            from_t = TrustLevel(first_entry["from"])
            to_t = TrustLevel(first_entry["to"])
        except ValueError as e:
            raise ContractValidationError(f"Invalid trust value in history: {e}") from e

        if from_t == to_t:
            raise ContractValidationError("Trust transition cannot have identical source and target.")
        validate_trust_transition(from_t, to_t)

        prev_time = _parse_timestamp(first_entry["timestamp"])
        current_t = to_t

        for entry in history[1:]:
            self.validate_entry(entry)

            curr_time = _parse_timestamp(entry["timestamp"])
            if curr_time <= prev_time:
                raise ContractValidationError("Trust history timestamps must be strictly monotonic (increasing).")
            prev_time = curr_time

            try:
                from_t = TrustLevel(entry["from"])
                to_t = TrustLevel(entry["to"])
            except ValueError as e:
                raise ContractValidationError(f"Invalid trust value in history: {e}") from e

            if from_t == to_t:
                raise ContractValidationError("Trust transition cannot have identical source and target.")
            if from_t != current_t:
                raise ContractValidationError(f"Trust history discontinuity: expected previous trust '{current_t}', got '{from_t}'.")

            validate_trust_transition(from_t, to_t)
            current_t = to_t

        if current_t != current_trust:
            validate_trust_transition(current_t, current_trust)


def validate_state_history_sequence(history: Tuple[Mapping[str, Any], ...], current_state: ContractState) -> None:
    StateHistoryValidator().validate(history, current_state)


def validate_trust_history_sequence(history: Tuple[Mapping[str, Any], ...], current_trust: TrustLevel) -> None:
    TrustHistoryValidator().validate(history, current_trust)
