import unittest
from storage.contract_store import ContractStore
from contracts.strategy_validation import StrategyValidationContract
from replay.replay_engine import DecisionReplayEngine

class TestVSC1_4ReplayEngine(unittest.TestCase):

    def test_decision_replay(self):
        print("\n==================================================")
        print(" Starting VSC 1.4 Decision Replay Engine Test")
        print("==================================================")

        store = ContractStore()
        root_id = "root-uuid-1234-5678"

        # Simulate sequential contracts sharing a root lineage
        c1 = StrategyValidationContract(
            root_contract_id=root_id,
            strategy_id="STRAT-REPLAY-001",
            status="APPROVED"
        )
        c2 = StrategyValidationContract(
            root_contract_id=root_id,
            strategy_id="STRAT-REPLAY-002",
            status="APPROVED"
        )

        store.save_contract(c1)
        store.save_contract(c2)

        # Replay decision chain from root ID
        engine = DecisionReplayEngine(store)
        chain = engine.replay(root_id)

        print(f"Replayed Root ID        : {root_id}")
        print(f"Reconstructed Chain Len : {len(chain)}")
        for idx, item in enumerate(chain):
            print(f"  [{idx+1}] {item['contract_class']} -> Strategy: {item['data']['strategy_id']}")

        print("-" * 52)
        print("==================================================")
        print(" 🎉 VSC 1.4 Decision Replay Engine Verified!")
        print("==================================================")

        # Invariant Assertions
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0]["data"]["strategy_id"], "STRAT-REPLAY-001")
        self.assertEqual(chain[1]["data"]["strategy_id"], "STRAT-REPLAY-002")

if __name__ == "__main__":
    unittest.main()
