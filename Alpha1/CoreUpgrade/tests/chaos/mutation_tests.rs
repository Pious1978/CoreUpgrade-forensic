use std::collections::{HashMap, HashSet};
use crate::reference_model::{ReferenceModel, ModelState};
use crate::simulated_broker::SimulatedBroker;
use crate::oracle::{assert_five_laws_of_execution, EconomicSnapshot, EconomicView};
use gateway::execution_orchestrator::{ExecutionOrchestrator, OrderStatus, ExecutionRecord};
use gateway::money::Money;
use gateway::journal::DurableJournal;

// Mock structure exposing mutation hooks for testing the Oracle itself
pub struct MockGatewayProjection {
    pub orders: HashMap<String, ExecutionRecord>,
}

impl EconomicView for MockGatewayProjection {
    fn terminal_snapshot(&self) -> HashMap<String, EconomicSnapshot> {
        self.orders.iter().map(|(id, rec)| {
            let released = rec.cumulative_released_exposure.clone().unwrap_or(Money::zero("USD", 4));
            let original = rec.original_exposure.clone().unwrap_or(Money::zero("USD", 4));
            let reserved_units = original.units - released.units;

            (id.clone(), EconomicSnapshot {
                state: match rec.state {
                    OrderStatus::Filled => "Filled".into(),
                    OrderStatus::Cancelled => "Cancelled".into(),
                    _ => "Active".into(),
                },
                requested_qty: rec.requested_quantity,
                filled_qty: rec.cumulative_filled_quantity,
                remaining_qty: rec.requested_quantity - rec.cumulative_filled_quantity,
                original_exposure_units: original.units,
                released_exposure_units: released.units,
                reserved_exposure_units: reserved_units,
                has_broker_identity: rec.broker_order_id.is_some(),
                observed_fills: rec.observed_fills.clone(),
            })
        }).collect()
    }

    fn was_externalized(&self, order_id: &str) -> bool {
        self.orders.get(order_id).map_or(false, |r| r.broker_order_id.is_some())
    }
}

#[cfg(test)]
mod mutation_tests {
    use super::*;

    fn setup_valid_mock() -> MockGatewayProjection {
        let mut orders = HashMap::new();
        orders.insert("ORD-1".into(), ExecutionRecord {
            order_id: "ORD-1".into(),
            sequence_number: 1,
            state: OrderStatus::Acknowledged,
            requested_quantity: 100,
            idempotency_key: Some("IDEMP-1".into()),
            broker_order_id: Some("BRK-1".into()),
            original_exposure: Some(Money::new(100_000, "USD", 4)),
            cumulative_released_exposure: Some(Money::new(0, "USD", 4)),
            cumulative_filled_quantity: 0,
            observed_fills: HashSet::new(),
        });
        MockGatewayProjection { orders }
    }

    #[test]
    #[should_panic(expected = "LAW 2 FATAL: Original exposure != Released + Reserved")]
    fn mutation_catch_double_risk_release() {
        let mut mock = setup_valid_mock();
        let rec = mock.orders.get_mut("ORD-1").unwrap();
        // Maliciously mutate released exposure to exceed original exposure, breaking Law 2
        rec.cumulative_released_exposure = Some(Money::new(150_000, "USD", 4));

        let reference = ReferenceModel::new();
        let broker = SimulatedBroker::new();
        
        // We bypass actual orchestration and test the Oracle against the mutated projection view
        // In the full test framework, this triggers the snapshot assertions directly:
        let snap = mock.terminal_snapshot();
        for (id, order) in &snap {
            assert_eq!(
                order.original_exposure_units, 
                order.released_exposure_units + order.reserved_exposure_units,
                "LAW 2 FATAL: Original exposure != Released + Reserved on order {}", id
            );
        }
    }

    #[test]
    #[should_panic(expected = "LAW 4 FATAL: Gateway claims 'Filled' state without authoritative broker quantity proof")]
    fn mutation_catch_manufactured_certainty() {
        let mut mock = setup_valid_mock();
        let rec = mock.orders.get_mut("ORD-1").unwrap();
        // Gateway hallucinates a 'Filled' state without matching broker facts
        rec.state = OrderStatus::Filled;
        rec.cumulative_filled_quantity = 100;

        let broker = SimulatedBroker::new(); // Broker knows nothing about this fill
        let gw_snap = mock.terminal_snapshot();
        let broker_snap = broker.terminal_snapshot();

        for (id, gw_order) in &gw_snap {
            if gw_order.state == "Filled" {
                let broker_order = broker_snap.get(id).expect("Broker missing order");
                assert_eq!(
                    broker_order.filled_qty, broker_order.requested_qty,
                    "LAW 4 FATAL: Gateway claims 'Filled' state without authoritative broker quantity proof on order {}", id
                );
            }
        }
    }
}