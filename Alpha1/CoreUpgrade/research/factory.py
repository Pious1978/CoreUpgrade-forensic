from contracts.research import ResearchSignalContract
from .adapter import ResearchCandidate

class ResearchSignalFactory:
    """Translates internal research candidates into immutable platform contracts."""
    def create(self, candidate: ResearchCandidate, root_id, correlation_id) -> ResearchSignalContract:
        initial_weight = round(min(max(candidate.score * 0.2, 0.05), 0.25), 2)
        return ResearchSignalContract(
            root_contract_id=root_id,
            correlation_id=correlation_id,
            signal_id=f"sig-{candidate.symbol}-2026-08",
            symbol=candidate.symbol,
            suggested_weight=initial_weight,
            confidence_score=candidate.confidence,
            expected_return=0.08
        )
