import unittest
from storage.contract_store import ContractStore
from contracts.strategy_validation import StrategyValidationContract

class TestVSC1_3Persistence(unittest.TestCase):

    def test_contract_store_and_audit_persistence(self):
        print("\n==================================================")
        print(" Starting VSC 1.3 Persistence & Event Store Test")
        print("==================================================")

        store = ContractStore()

        # Create and save a validation contract
        contract = StrategyValidationContract(
            strategy_id="STRAT-PERSIST-001",
            status="APPROVED",
            validation_score=1.0,
            failures=()
        )

        contract_id = store.save_contract(contract)
        print(f"Persisted Contract ID   : {contract_id}")

        retrieved = store.get_contract(contract_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["class"], "StrategyValidationContract")
        print(f"Retrieved Contract Type : {retrieved['class']}")

        events = store.get_event_stream()
        print(f"Audit Event Count       : {len(events)}")
        self.assertGreaterEqual(len(events), 1)

        print("-" * 52)
        print("==================================================")
        print(" 🎉 VSC 1.3 Persistence & Event Store Verified!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
