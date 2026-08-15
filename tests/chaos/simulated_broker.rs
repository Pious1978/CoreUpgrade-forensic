use std::collections::{HashMap, HashSet};
use gateway::execution_orchestrator::{EconomicSnapshot, EconomicView};
use gateway::money::Money;
use gateway::execution_events::BrokerFactEvent;

#[derive(Debug, Clone)]
pub struct BrokerOrder {
    pub order_id: String,
    pub broker_order_id: String,
    pub requested_qty: u64,
    pub filled_qty: u64,
    pub state: String,
    pub observed_fills: HashSet<String>,
    pub original_exposure: Money,
}

pub struct SimulatedBroker {
    orders: HashMap<String, BrokerOrder>,
}

impl EconomicView for SimulatedBroker {
    fn projected_snapshot(&self) -> HashMap<String, EconomicSnapshot> {
        self.orders.iter().map(|(id, ord)| {
            assert!(ord.requested_qty > 0, "FATAL BROKER: requested quantity is zero for {}", id);
            assert!(ord.filled_qty <= ord.requested_qty, "FATAL BROKER: filled quantity exceeds requested quantity for {}", id);

            let released_units = (ord.original_exposure.units * ord.filled_qty as i128) / ord.requested_qty as i128;
            let reserved_units = ord.original_exposure.units - released_units;
            let remaining_qty = ord.requested_qty.checked_sub(ord.filled_qty).expect("FATAL BROKER: quantity underflow");

            (
                id.clone(),
                EconomicSnapshot {
                    state: ord.state.clone(),
                    requested_qty: ord.requested_qty,
                    filled_qty: ord.filled_qty,
                    remaining_qty,
                    original_exposure_units: ord.original_exposure.units,
                    released_exposure_units: released_units,
                    reserved_exposure_units: reserved_units,
                    has_broker_identity: true,
                    observed_fills: ord.observed_fills.clone(),
                },
            )
        }).collect()
    }
}

impl SimulatedBroker {
    pub fn new() -> Self {
        Self { orders: HashMap::new() }
    }

    pub fn broker_order_id_for(order_id: u8) -> String {
        format!("BROKER-{}", order_id)
    }

    pub fn get_order(&self, order_id: &str) -> Option<&BrokerOrder> {
        self.orders.get(order_id)
    }

    pub fn orders(&self) -> &HashMap<String, BrokerOrder> {
        &self.orders
    }

    pub fn terminal_snapshot(&self) -> HashMap<String, EconomicSnapshot> {
        self.projected_snapshot()
    }

    pub async fn inject_adversarial_fact(&mut self, fact: &BrokerFactEvent) {
        match fact {
            BrokerFactEvent::Accepted { order_id, broker_order_id, requested_quantity, original_exposure } => {
                if broker_order_id.trim().is_empty() || *requested_quantity == 0 || original_exposure.units < 0 {
                    return;
                }

                let id_str = format!("ORD-{}", order_id);

                if let Some(existing) = self.orders.get(&id_str) {
                    if existing.broker_order_id != *broker_order_id
                        || existing.requested_qty != *requested_quantity
                        || existing.original_exposure != *original_exposure
                    {
                        panic!("FATAL BROKER CONTRADICTION: Accepted payload for {} changed immutable identity", id_str);
                    }
                    return;
                }

                if self.orders.values().any(|e| e.broker_order_id == *broker_order_id && e.order_id != id_str) {
                    panic!("FATAL BROKER IDENTITY VIOLATION: broker_order_id {} claimed by multiple orders", broker_order_id);
                }

                self.orders.insert(id_str.clone(), BrokerOrder {
                    order_id: id_str,
                    broker_order_id: broker_order_id.clone(),
                    requested_qty: *requested_quantity,
                    filled_qty: 0,
                    state: "Acknowledged".to_string(),
                    observed_fills: HashSet::new(),
                    original_exposure: original_exposure.clone(),
                });
            }

            BrokerFactEvent::Rejected { order_id, .. } => {
                let id_str = format!("ORD-{}", order_id);
                let Some(ord) = self.orders.get_mut(&id_str) else { return; };
                if matches!(ord.state.as_str(), "Filled" | "Cancelled" | "Rejected") {
                    return;
                }
                ord.state = "Rejected".to_string();
            }

            BrokerFactEvent::Fill { order_id, fill_id, quantity, remaining, price } => {
                let id_str = format!("ORD-{}", order_id);
                let Some(ord) = self.orders.get_mut(&id_str) else { return; };

                if fill_id.trim().is_empty() || *quantity == 0 {
                    return;
                }
                if price.currency != ord.original_exposure.currency || price.scale != ord.original_exposure.scale {
                    return;
                }
                if matches!(ord.state.as_str(), "Filled" | "Cancelled" | "Rejected") {
                    return;
                }

                if ord.observed_fills.contains(fill_id) {
                    return;
                }

                let new_filled = match ord.filled_qty.checked_add(*quantity) {
                    Some(v) => v,
                    None => return,
                };
                if new_filled > ord.requested_qty { return; }

                let expected_remaining = match ord.requested_qty.checked_sub(new_filled) {
                    Some(v) => v,
                    None => return,
                };
                if expected_remaining != *remaining { return; }

                ord.filled_qty = new_filled;
                ord.observed_fills.insert(fill_id.clone());
                ord.state = if expected_remaining == 0 { "Filled".to_string() } else { "PartiallyFilled".to_string() };
            }

            BrokerFactEvent::CancelConfirmed { order_id, remaining } => {
                let id_str = format!("ORD-{}", order_id);
                let Some(ord) = self.orders.get_mut(&id_str) else { return; };

                if matches!(ord.state.as_str(), "Filled" | "Cancelled" | "Rejected") {
                    return;
                }

                let expected_remaining = match ord.requested_qty.checked_sub(ord.filled_qty) {
                    Some(v) => v,
                    None => return,
                };
                if expected_remaining != *remaining { return; }

                ord.state = "Cancelled".to_string();
            }
        }
    }
}