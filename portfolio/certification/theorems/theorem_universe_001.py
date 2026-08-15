# portfolio/certification/theorems/theorem_universe_001.py
from portfolio.contracts.portfolio_certificate import PortfolioCertificate
from portfolio.contracts.universe_contract import UniverseCertificate

class UniverseTradabilityTheorem:
    id = "THEOREM-UNIVERSE-001"
    
    @classmethod
    def verify(cls, portfolio_cert: PortfolioCertificate, universe_cert: UniverseCertificate) -> dict:
        """
        Invariant 1: Portfolio asset must exist in the UniverseCertificate.
        Invariant 2: Certificate hashes must match perfectly.
        """
        if portfolio_cert.universe_hash != universe_cert.certificate_hash:
            return {"certified": False, "reason": "Universe Hash Mismatch."}
            
        universe_asset_ids = {a.instrument_id for a in universe_cert.assets}
        
        for target in portfolio_cert.target_weights:
            # Check 1: Membership
            if target.instrument_id not in universe_asset_ids:
                return {
                    "certified": False, 
                    "reason": f"Allocation to ineligible asset: {target.instrument_id}"
                }
                
        # (Check 2 & 3: Temporal Validity & Rule Compliance are proven via THEOREM-UNIVERSE-REPLAY-001)
        return {"certified": True}

# portfolio/certification/theorems/theorem_universe_replay_001.py
from portfolio.universe.certificate_engine import UniverseCertificateEngine

class UniverseReplayTheorem:
    id = "THEOREM-UNIVERSE-REPLAY-001"
    
    @classmethod
    def verify(
        cls, 
        original_certificate: 'UniverseCertificate', 
        definition: 'UniverseDefinition', 
        active_filters: tuple,
        metadata: 'PointInTimeMetadata', 
        base_population: 'PointInTimeBasePopulation'
    ) -> dict:
        """
        Invariant: Given the exact same definitions and metadata snapshot hash,
        generation must yield an identical cryptographic certificate.
        """
        replayed_cert = UniverseCertificateEngine.generate(
            definition, active_filters, metadata, base_population, original_certificate.timestamp
        )
        
        if replayed_cert.certificate_hash != original_certificate.certificate_hash:
            return {
                "certified": False, 
                "reason": "Universe generation is non-deterministic or metadata drifted.",
                "original_hash": original_certificate.certificate_hash,
                "replayed_hash": replayed_cert.certificate_hash
            }
            
        return {"certified": True}
