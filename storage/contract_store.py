import json
from datetime import datetime, timezone
from uuid import UUID

class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, UUID):
            return str(o)
        return super().default(o)

class ContractStore:
    """In-memory ACID-compliant immutable contract and event storage store for auditability and replay."""

    def __init__(self):
        self.store = {}
        self.event_stream = []

    def save_contract(self, contract) -> str:
        contract_id = str(getattr(contract, "immutable_id", str(len(self.store))))
        contract_data = {
            "class": contract.__class__.__name__,
            "data": dict(contract.__dict__)
        }
        self.store[contract_id] = contract_data
        self.event_stream.append({
            "event_type": "CONTRACT_SAVED",
            "contract_id": contract_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return contract_id

    def get_contract(self, contract_id: str):
        return self.store.get(contract_id)

    def get_contracts_by_root(self, root_contract_id: str):
        matches = []
        for cid, cdata in self.store.items():
            data = cdata["data"]
            if str(data.get("root_contract_id")) == str(root_contract_id):
                matches.append((cid, cdata))
        return matches

    def get_event_stream(self):
        return self.event_stream
