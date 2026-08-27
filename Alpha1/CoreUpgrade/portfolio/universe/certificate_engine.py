# portfolio/universe/certificate_engine.py
from datetime import datetime
from typing import Tuple
from portfolio.universe.universe_definition import UniverseDefinition
from portfolio.universe.metadata_provider import PointInTimeMetadata, PointInTimeBasePopulation
from portfolio.universe.eligibility_rules import UniverseFilter
from portfolio.contracts.universe_contract import UniverseCertificate

class UniverseCertificateEngine:
    @staticmethod
    def generate(
        definition: UniverseDefinition,
        active_filters: Tuple[UniverseFilter, ...], 
        metadata: PointInTimeMetadata, 
        base_population: PointInTimeBasePopulation,
        timestamp: datetime
    ) -> UniverseCertificate:
        
        # 1. Retrieve Point-In-Time Reality (No Survivorship Bias)
        base_assets = base_population.members_at(timestamp)
        
        # 2. Apply Filters
        eligible_assets = []
        for asset in base_assets:
            if all(f.evaluate(asset, metadata) for f in active_filters):
                eligible_assets.append(asset)
                
        # 3. Deterministic Sorting (by instrument_id) ensures identical hashes
        eligible_assets = tuple(sorted(eligible_assets, key=lambda a: a.instrument_id))
        
        # 4. Mint Certificate
        return UniverseCertificate(
            universe_id=f"{definition.definition_id}-{timestamp.strftime('%Y%m%d')}",
            timestamp=timestamp,
            assets=eligible_assets,
            ruleset_hash=definition.ruleset_hash,
            metadata_snapshot_hash=metadata.snapshot_hash
        )
