use std::collections::{HashMap, HashSet};
use gateway::execution_orchestrator::{EconomicSnapshot, EconomicView};
use gateway::money::Money;
use gateway::execution_events::{BrokerFactEvent, GatewayCommand};

#[derive(Clone)]
pub struct ReferenceOrder {
    pub order_id: String,
    pub requested_qty: u64,
    pub filled_qty: u64,
    pub original_exposure: Money,
    pub state: String,
    pub observed_fills: HashSet<String>,
    pub externalized: bool,
    pub broker_order_id: Option<String>,
}

impl ReferenceOrder {
    fn is_terminal(&self) -> bool {
        matches!(self.state.as_str(), "Filled" | "BrokerRejected" | "Cancelled")
    }

    fn remaining_qty(&self) -> u64 {
        self.requested_qty.checked_sub(self.filled_qty).expect("FATAL REFERENCE: quantity underflow")
    }
}

pub struct ReferenceModel {
    orders: HashMap<String, ReferenceOrder>,
}

impl EconomicView for ReferenceModel {
    fn projected_snapshot(&self) -> HashMap<String, EconomicSnapshot> {
        self.orders.iter().map(|(id, ord)| {
            assert!(ord.requested_qty > 0, "FATAL REFERENCE: requested quantity is zero for {}", id);
            assert!(ord.filled_qty <= ord.requested_qty, "FATAL REFERENCE: filled > requested for {}", id);

            let released_units = (ord.original_exposure.units * ord.filled_qty as i128) / ord.requested_qty as i128;
            let reserved_units = ord.original_exposure.units - released_units;

            (
                id.clone(),
                EconomicSnapshot {
                    state: ord.state.clone(),
                    requested_qty: ord.requested_qty,
                    filled_qty: ord.filled_qty,
                    remaining_qty: ord.remaining_qty(),
                    original_exposure_units: ord.original_exposure.units,
                    released_exposure_units: released_units,
                    reserved_exposure_units: reserved_units,
                    has_broker_identity: ord.broker_order_id.is_some(),
                    observed_fills: ord.observed_fills.clone(),
                },
            )
        }).collect()
    }
}

impl ReferenceModel {
    pub fn new() -> Self {
        Self { orders: HashMap::new() }
    }

    pub fn was_externalized(&self, order_id: &str) -> bool {
        self.orders.get(order_id).map(|o| o.externalized).unwrap_or(false)
    }

    pub fn get_order(&self, order_id: &str) -> Option<&ReferenceOrder> {
        self.orders.get(order_id)
    }

    pub fn apply_command(&mut self, cmd: &GatewayCommand) -> Result<(), String> {
        match cmd {
            GatewayCommand::Admit { order_id, quantity, exposure } => {
                if format!("{}", order_id).trim().is_empty() || *quantity == 0 {
                    return Err("FATAL REFERENCE: invalid admission parameters".into());
                }
                let id_str = format!("ORD-{}", order_id);
                if self.orders.contains_key(&id_str) {
                    return Err(format!("FATAL REFERENCE: duplicate order {}", id_str));
                }

                let original_exposure = Money::new(*exposure as i128, "USD", 4);
                if original_exposure.units < 0 {
                    return Err("FATAL REFERENCE: negative exposure".into());
                }

                self.orders.insert(id_str.clone(), ReferenceOrder {
                    order_id: id_str,
                    requested_qty: *quantity,
                    filled_qty: 0,
                    original_exposure,
                    state: "Admitted".to_string(),
                    observed_fills: HashSet::new(),
                    externalized: false,
                    broker_order_id: None,
                });
            }
            GatewayCommand::Submit { order_id } => {
                let id_str = format!("ORD-{}", order_id);
                let ord = self.orders.get_mut(&id_str).ok_or_else(|| format!("FATAL REFERENCE: order {} not found", id_str))?;

                if ord.is_terminal() {
                    return Err(format!("FATAL REFERENCE: cannot submit terminal order {}", id_str));
                }

                match ord.state.as_str() {
                    "Admitted" | "RiskReserved" => { ord.state = "SubmissionPending".to_string(); }
                    "SubmissionPending" | "Unknown" => {} // Idempotent
                    _ => return Err(format!("FATAL REFERENCE: illegal Submit transition from {}", ord.state)),
                }
            }
            GatewayCommand::Cancel { order_id } => {
                let id_str = format!("ORD-{}", order_id);
                let ord = self.orders.get_mut(&id_str).ok_or_else(|| format!("FATAL REFERENCE: order {} not found", id_str))?;

                match ord.state.as_str() {
                    "Acknowledged" | "PartiallyFilled" => { ord.state = "CancelPending".to_string(); }
                    "CancelPending" | "CancelUnknown" => {} // Idempotent
                    _ => return Err(format!("FATAL REFERENCE: illegal Cancel transition from {}", ord.state)),
                }
            }
        }
        Ok(())
    }

    pub fn apply_fact(&mut self, fact: &BrokerFactEvent) -> Result<(), String> {
        match fact {
            BrokerFactEvent::Accepted { order_id, broker_order_id, requested_quantity, original_exposure } => {
                let id_str = format!("ORD-{}", order_id);
                if broker_order_id.trim().is_empty() || *requested_quantity == 0 {
                    return Err("FATAL REFERENCE: invalid acceptance parameters".into());
                }

                let ord = self.orders.get_mut(&id_str).ok_or_else(|| format!("FATAL REFERENCE: order {} not found", id_str))?;

                if ord.requested_qty != *requested_quantity || ord.original_exposure != *original_exposure {
                    return Err(format!("FATAL REFERENCE: accepted economic payload mutation for {}", id_str));
                }

                if let Some(existing) = &ord.broker_order_id {
                    if existing != broker_order_id {
                        return Err(format!("FATAL REFERENCE: broker identity mutation for {}", id_str));
                    }
                } else {
                    ord.broker_order_id = Some(broker_order_id.clone());
                }

                ord.externalized = true;

                match ord.state.as_str() {
                    "SubmissionPending" | "Unknown" => { ord.state = "Acknowledged".to_string(); }
                    "Acknowledged" | "PartiallyFilled" | "CancelPending" | "CancelUnknown" => {}
                    _ => return Err(format!("FATAL REFERENCE: illegal Accepted transition from {}", ord.state)),
                }
            }
            BrokerFactEvent::Rejected { order_id, .. } => {
                let id_str = format!("ORD-{}", order_id);
                let ord = self.orders.get_mut(&id_str).ok_or_else(|| format!("FATAL REFERENCE: order {} not found", id_str))?;
                if ord.is_terminal() { return Err("FATAL REFERENCE: rejection for terminal order".into()); }

                match ord.state.as_str() {
                    "SubmissionPending" | "Unknown" | "Acknowledged" => { ord.state = "BrokerRejected".to_string(); }
                    _ => return Err(format!("FATAL REFERENCE: illegal rejection transition from {}", ord.state)),
                }
            }
            BrokerFactEvent::Fill { order_id, fill_id, quantity, remaining, price } => {
                let id_str = format!("ORD-{}", order_id);
                if fill_id.trim().is_empty() || *quantity == 0 {
                    return Err("FATAL REFERENCE: invalid fill parameters".into());
                }

                let ord = self.orders.get_mut(&id_str).ok_or_else(|| format!("FATAL REFERENCE: order {} not found", id_str))?;
                if ord.is_terminal() || !ord.externalized {
                    return Err("FATAL REFERENCE: invalid fill state".into());
                }

                if price.currency != ord.original_exposure.currency || price.scale != ord.original_exposure.scale {
                    return Err("FATAL REFERENCE: fill price currency/scale mismatch".into());
                }

                if ord.observed_fills.contains(fill_id) {
                    return Ok(());
                }

                let new_filled = ord.filled_qty.checked_add(*quantity).ok_or("FATAL REFERENCE: fill quantity overflow")?;
                if new_filled > ord.requested_qty { return Err("FATAL REFERENCE: fills exceed requested quantity".into()); }

                let expected_remaining = ord.requested_qty.checked_sub(new_filled).ok_or("FATAL REFERENCE: remaining quantity underflow")?;
                if expected_remaining != *remaining { return Err("FATAL REFERENCE: remaining quantity mismatch".into()); }

                ord.filled_qty = new_filled;
                ord.observed_fills.insert(fill_id.clone());
                ord.state = if expected_remaining == 0 { "Filled".to_string() } else { "PartiallyFilled".to_string() };
            }
            BrokerFactEvent::CancelConfirmed { order_id, remaining } => {
                let id_str = format!("ORD-{}", order_id);
                let ord = self.orders.get_mut(&id_str).ok_or_else(|| format!("FATAL REFERENCE: order {} not found", id_str))?;
                if ord.is_terminal() { return Err("FATAL REFERENCE: cancellation for terminal order".into()); }

                if ord.remaining_qty() != *remaining {
                    return Err("FATAL REFERENCE: cancellation remaining mismatch".into());
                }
                ord.state = "Cancelled".to_string();
            }
        }
        Ok(())
    }
}