import unittest
from dataclasses import FrozenInstanceError
from .pipeline import (
    VSCPipeline,
    ResearchGeneratorComponent,
    GovernanceComponent,
    PortfolioIntentComponent,
    PortfolioRiskComponent,
    ExecutionPlanningComponent,
    BrokerExecutionComponent,
    FeedbackComponent,
)
from .invariants import (
    VSC_PIPELINE_VERSION,
    STRUCTURAL_INVARIANTS,
    BUSINESS_INVARIANTS,
    TrustLevel,
    LifecycleState,
)

class TestVerticalSliceCompleteRefactored(unittest.TestCase):

    def test_end_to_end_pipeline(self):
        print("\n==================================================")
        print(" Starting VSC 1.1 Baseline Milestone Verification")
        print("==================================================")

        self.assertEqual(VSC_PIPELINE_VERSION, "1.0")

        pipeline = VSCPipeline(
            research_gen=ResearchGeneratorComponent(),
            governance=GovernanceComponent(),
            intent_stage=PortfolioIntentComponent(),
            risk_stage=PortfolioRiskComponent(),
            planning_stage=ExecutionPlanningComponent(),
            broker_stage=BrokerExecutionComponent(),
            feedback_stage=FeedbackComponent()
        )
        
        pipeline_result = pipeline.run()
        contracts = pipeline_result.contracts
        telemetry = pipeline_result.telemetry
        signal, approved, intent, decision, plan, result, feedback = contracts

        root_id = signal.root_contract_id
        corr_id = signal.correlation_id

        # 1. Verify Immutability
        with self.assertRaises(FrozenInstanceError):
            signal.symbol = "MSFT"

        # 2. Structural Invariants: Chain Length
        expected_len = STRUCTURAL_INVARIANTS["chain_length"]
        self.assertEqual(len(contracts), expected_len)

        # 3. Structural Invariants: Contract Types Sequence
        expected_types = STRUCTURAL_INVARIANTS["contract_types"]
        for c, expected_type in zip(contracts, expected_types):
            self.assertIsInstance(c, expected_type)

        # 4. Schema Validation Guardrail (Prevents Core Attribute Drift)
        required_attributes = [
            "immutable_id", "root_contract_id", "parent_contract_id", 
            "correlation_id", "version", "created_at", 
            "domain", "trust_level", "lifecycle_state"
        ]
        for i, c in enumerate(contracts):
            for attr in required_attributes:
                self.assertTrue(
                    hasattr(c, attr), 
                    f"Contract {c.contract_type} at index {i} is missing required core schema attribute: {attr}"
                )

        # 5. Lineage Graph Integrity & Uniqueness
        visited_ids = set()
        for i, c in enumerate(contracts):
            self.assertNotIn(c.immutable_id, visited_ids)
            visited_ids.add(c.immutable_id)
            
            self.assertEqual(c.root_contract_id, root_id)
            self.assertEqual(c.correlation_id, corr_id)
            self.assertIsNotNone(c.immutable_id)
            self.assertEqual(c.version, 1)

            if i > 0:
                self.assertEqual(c.parent_contract_id, contracts[i-1].immutable_id)

        # 6. Verify Timestamps
        for i in range(1, len(contracts)):
            self.assertGreaterEqual(contracts[i].created_at, contracts[i-1].created_at)

        # 7. Business Invariants
        expected_trusts = BUSINESS_INVARIANTS["trust_transitions"]
        for c, expected_trust in zip(contracts, expected_trusts):
            self.assertEqual(TrustLevel(c.trust_level), expected_trust)

        expected_states = BUSINESS_INVARIANTS["lifecycle_states"]
        for c, expected_state in zip(contracts, expected_states):
            self.assertEqual(LifecycleState(c.lifecycle_state), expected_state)

        expected_domains = BUSINESS_INVARIANTS["domain_sequence"]
        for c, expected_domain in zip(contracts, expected_domains):
            self.assertEqual(c.domain, expected_domain)

        # Operational Stage Telemetry Table
        print("\n--- Operational Stage Metrics Telemetry ---")
        print(f"{'Stage Name':<22} | {'Duration (ms)':<14} | {'Input Type':<20} | {'Output Contract':<28}")
        print("-" * 92)
        for m in telemetry.metrics:
            print(f"{m.stage_name:<22} | {m.duration_ms:<14.3f} | {m.input_type:<20} | {m.output_type:<28}")
        print("-" * 92)

        # Chain Visualization Tool
        print("\n--- Canonical Contract Chain Visualization (VSC 1.1) ---")
        for i, c in enumerate(contracts):
            indent = "  " * i
            print(f"{indent}└─► [{c.contract_type}] (Domain: {c.domain}, ID: {str(c.immutable_id)[:8]}..., Trust: {c.trust_level}, State: {c.lifecycle_state})")
        print("------------------------------------------------------")

        print("==================================================")
        print(" 🎉 VSC 1.1 Baseline Milestone Verified Successfully!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
