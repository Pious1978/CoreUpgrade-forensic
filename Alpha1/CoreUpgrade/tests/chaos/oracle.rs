use std::collections::HashMap;
use crate::reference_model::ReferenceModel;
use crate::simulated_broker::SimulatedBroker;
use gateway::execution_orchestrator::{
    EconomicSnapshot,
    EconomicView,
    ExecutionOrchestrator,
};
use gateway::journal::{
    DurableJournal,
    TransactionRecord,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JournalPosition {
    pub transaction_id: u64,
    pub previous_hash: String,
    pub transaction_hash: String,
}

pub fn is_committed_prefix(
    journal_path: &str,
    t1: &JournalPosition,
    t2: &JournalPosition,
) -> bool {
    if t2.transaction_id < t1.transaction_id {
        return false;
    }
    if t1.transaction_id == 0 {
        return true;
    }

    let records = match recover_verified_records_from_disk(journal_path) {
        Ok(records) => records,
        Err(_) => return false,
    };

    let mut t1_found = false;
    let mut t2_found = false;
    let mut expected_previous_hash = "GENESIS_HASH_000000000000000000000000000000000000000000000000".to_string();
    let mut previous_tx_id: Option<u64> = None;

    for record in records.iter() {
        if let Some(previous_id) = previous_tx_id {
            if record.transaction_id <= previous_id {
                return false;
            }
        }
        previous_tx_id = Some(record.transaction_id);

        if record.previous_hash != expected_previous_hash {
            return false;
        }

        if record.transaction_id == t1.transaction_id {
            if record.previous_hash != t1.previous_hash || record.checksum != t1.transaction_hash {
                return false;
            }
            t1_found = true;
        }

        if record.transaction_id == t2.transaction_id {
            if record.previous_hash != t2.previous_hash || record.checksum != t2.transaction_hash {
                return false;
            }
            t2_found = true;
        }

        expected_previous_hash = record.checksum.clone();

        if t1_found && t2_found {
            return true;
        }
    }

    false
}

fn recover_verified_records_from_disk(
    journal_path: &str,
) -> Result<Vec<TransactionRecord>, String> {
    let mut journal = DurableJournal::new(journal_path);
    journal.recover_verified_records()
}

pub fn assert_five_laws_of_execution(
    reference: &ReferenceModel,
    broker: &SimulatedBroker,
    gateway: &ExecutionOrchestrator,
    journal_path: &str,
    t1_pos: Option<&JournalPosition>,
    t1_knowledge: Option<&HashMap<String, EconomicSnapshot>>,
    t2_pos: Option<&JournalPosition>,
    t2_knowledge: Option<&HashMap<String, EconomicSnapshot>>,
) {
    let ref_snap = reference.projected_snapshot();
    let broker_snap = broker.projected_snapshot();
    let gateway_snap = gateway.projected_snapshot();

    assert_law_1_durability(journal_path, &gateway_snap);
    assert_law_2_conservation(&gateway_snap);
    assert_law_3_economic_convergence(reference, &ref_snap, &broker_snap, &gateway_snap);
    assert_law_4_epistemic_soundness(&broker_snap, &gateway_snap);

    if let (Some(p1), Some(k1), Some(p2), Some(k2)) = (t1_pos, t1_knowledge, t2_pos, t2_knowledge) {
        assert_law_5_monotonic_knowledge(journal_path, p1, k1, p2, k2);
    }
}

fn assert_law_1_durability(
    journal_path: &str,
    live_snap: &HashMap<String, EconomicSnapshot>,
) {
    let journal = DurableJournal::new(journal_path);
    let recovered_gateway = ExecutionOrchestrator::recover_and_start(journal)
        .expect("LAW 1 FATAL: Journal recovery failed");

    let recovered_snap = recovered_gateway.projected_snapshot();
    assert_eq!(live_snap, &recovered_snap, "LAW 1 FATAL: Memory projection diverges from durable journal replay.");
}

fn assert_law_2_conservation(gateway_snap: &HashMap<String, EconomicSnapshot>) {
    for (id, order) in gateway_snap {
        assert!(order.filled_qty <= order.requested_qty, "LAW 2 FATAL: Filled > Requested on {}", id);

        let reconstructed_requested = order.filled_qty
            .checked_add(order.remaining_qty)
            .expect("LAW 2 FATAL: Quantity addition overflow");

        assert_eq!(order.requested_qty, reconstructed_requested, "LAW 2 FATAL: Filled + Remaining != Requested on {}", id);
        assert!(order.original_exposure_units >= 0, "LAW 2 FATAL: Negative original exposure on {}", id);
        assert!(order.released_exposure_units >= 0, "LAW 2 FATAL: Negative released exposure on {}", id);
        assert!(order.reserved_exposure_units >= 0, "LAW 2 FATAL: Negative reserved exposure on {}", id);

        assert_eq!(
            order.original_exposure_units,
            order.released_exposure_units + order.reserved_exposure_units,
            "LAW 2 FATAL: Original exposure != Released + Reserved on {}", id
        );
    }
}

fn assert_law_3_economic_convergence(
    reference: &ReferenceModel,
    ref_snap: &HashMap<String, EconomicSnapshot>,
    broker_snap: &HashMap<String, EconomicSnapshot>,
    gateway_snap: &HashMap<String, EconomicSnapshot>,
) {
    for (id, ref_order) in ref_snap {
        let gateway_order = gateway_snap.get(id).unwrap_or_else(|| panic!("LAW 3 FATAL: Gateway lost reference order {}", id));

        assert_eq!(ref_order.requested_qty, gateway_order.requested_qty, "LAW 3 FATAL: requested quantity divergence on {}", id);
        assert_eq!(ref_order.filled_qty, gateway_order.filled_qty, "LAW 3 FATAL: filled quantity divergence on {}", id);
        assert_eq!(ref_order.remaining_qty, gateway_order.remaining_qty, "LAW 3 FATAL: remaining quantity divergence on {}", id);
        assert_eq!(ref_order.original_exposure_units, gateway_order.original_exposure_units, "LAW 3 FATAL: original exposure divergence on {}", id);
        assert_eq!(ref_order.released_exposure_units, gateway_order.released_exposure_units, "LAW 3 FATAL: released exposure divergence on {}", id);
        assert_eq!(ref_order.reserved_exposure_units, gateway_order.reserved_exposure_units, "LAW 3 FATAL: reserved exposure divergence on {}", id);
        assert_eq!(ref_order.observed_fills, gateway_order.observed_fills, "LAW 3 FATAL: fill identity divergence on {}", id);

        if reference.was_externalized(id) {
            let broker_order = broker_snap.get(id).unwrap_or_else(|| panic!("LAW 3 FATAL: Broker missing externalized order {}", id));
            assert_eq!(gateway_order.filled_qty, broker_order.filled_qty, "LAW 3 FATAL: Gateway/Broker fill divergence on {}", id);
            assert_eq!(gateway_order.observed_fills, broker_order.observed_fills, "LAW 3 FATAL: Gateway/Broker fill identity divergence on {}", id);
        } else {
            assert!(!gateway_order.has_broker_identity, "LAW 3 FATAL: Gateway materialized non-externalized order {}", id);
            assert!(!broker_snap.contains_key(id), "LAW 3 FATAL: Broker possesses non-externalized order {}", id);
        }
    }
}

fn assert_law_4_epistemic_soundness(
    broker_snap: &HashMap<String, EconomicSnapshot>,
    gateway_snap: &HashMap<String, EconomicSnapshot>,
) {
    for (id, gateway_order) in gateway_snap {
        match broker_snap.get(id) {
            None => {
                assert!(!gateway_order.has_broker_identity, "LAW 4 FATAL: Gateway possesses broker identity absent from broker truth on {}", id);
                assert!(gateway_order.observed_fills.is_empty(), "LAW 4 FATAL: Gateway possesses fills without broker truth on {}", id);
            }
            Some(broker_order) => {
                assert!(gateway_order.observed_fills.is_subset(&broker_order.observed_fills), "LAW 4 FATAL: Gateway observed nonexistent fill on {}", id);
                assert!(gateway_order.filled_qty <= broker_order.filled_qty, "LAW 4 FATAL: Gateway claims more fills than broker truth on {}", id);

                match gateway_order.state.as_str() {
                    "Filled" => {
                        assert_eq!(broker_order.remaining_qty, 0, "LAW 4 FATAL: Gateway claims Filled while broker has remaining quantity on {}", id);
                        assert_eq!(broker_order.filled_qty, broker_order.requested_qty, "LAW 4 FATAL: Gateway claims Filled without complete broker quantity proof on {}", id);
                    }
                    "PartiallyFilled" => {
                        assert!(broker_order.filled_qty > 0, "LAW 4 FATAL: Gateway claims PartiallyFilled with zero broker fills on {}", id);
                        assert!(broker_order.remaining_qty > 0, "LAW 4 FATAL: Gateway claims PartiallyFilled with zero remaining quantity on {}", id);
                    }
                    "Cancelled" => {
                        assert_eq!(broker_order.state, "Cancelled", "LAW 4 FATAL: Gateway claims Cancelled without broker cancellation proof on {}", id);
                    }
                    "BrokerRejected" => {
                        assert_eq!(broker_order.state, "Rejected", "LAW 4 FATAL: Gateway claims BrokerRejected without broker rejection proof on {}", id);
                    }
                    _ => {}
                }
            }
        }
    }
}

pub fn assert_law_5_monotonic_knowledge(
    journal_path: &str,
    t1_pos: &JournalPosition,
    t1_knowledge: &HashMap<String, EconomicSnapshot>,
    t2_pos: &JournalPosition,
    t2_knowledge: &HashMap<String, EconomicSnapshot>,
) {
    assert!(is_committed_prefix(journal_path, t1_pos, t2_pos), "LAW 5 FATAL: Timelines are not cryptographically ancestor-related");

    for (id, order_t1) in t1_knowledge {
        let order_t2 = t2_knowledge.get(id).unwrap_or_else(|| {
            panic!("LAW 5 FATAL: Epistemic amnesia. Previously known order {} disappeared from descendant timeline", id);
        });

        if order_t1.has_broker_identity {
            assert!(order_t2.has_broker_identity, "LAW 5 FATAL: Broker identity vanished on {}", id);
        }

        assert!(order_t2.observed_fills.is_superset(&order_t1.observed_fills), "LAW 5 FATAL: Epistemic amnesia. Observed fills vanished on {}", id);
        assert!(order_t2.filled_qty >= order_t1.filled_qty, "LAW 5 FATAL: Filled quantity regressed on {}", id);
        assert_eq!(order_t1.requested_qty, order_t2.requested_qty, "LAW 5 FATAL: Requested quantity mutated on {}", id);
    }
}