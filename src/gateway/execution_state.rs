use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OrderStatus {
    Received,
    Authenticated,
    Admitted,           // Sequence & Nonce consumed
    RiskReserved,       // Capital/Notional exposure locked
    SubmissionPending,  // In-flight to broker
    Unknown,            // Network timeout / disconnect (Requires Reconciliation)
    Acknowledged,       // Broker confirmed receipt
    Executed,           // Fill confirmed
    Rejected,           // Rejected by gateway, risk, or broker
}

#[derive(Debug, Clone)]
pub struct ExecutionRecord {
    pub order_id: String,             // E.g., ORD-93821
    pub sequence: u64,
    pub idempotency_key: String,      // The UDS nonce
    pub certificate_generation: u64,
    pub authorization_timestamp: f64,
    pub state: OrderStatus,
    pub notional_exposure: f64,
}

pub struct ExecutionStateManager {
    active_orders: HashMap<String, ExecutionRecord>,
    total_pending_exposure: f64,
}

impl ExecutionStateManager {
    pub fn new() -> Self {
        Self {
            active_orders: HashMap::new(),
            total_pending_exposure: 0.0,
        }
    }

    pub fn transition_state(&mut self, order_id: &str, new_state: OrderStatus) -> Result<(), String> {
        let record = self.active_orders.get_mut(order_id)
            .ok_or_else(|| format!("Order {} not found", order_id))?;

        // State Machine Invariants
        match (&record.state, &new_state) {
            (OrderStatus::RiskReserved, OrderStatus::SubmissionPending) |
            (OrderStatus::SubmissionPending, OrderStatus::Unknown) |
            (OrderStatus::SubmissionPending, OrderStatus::Acknowledged) |
            (OrderStatus::Unknown, OrderStatus::Executed) |
            (OrderStatus::Unknown, OrderStatus::Rejected) => {
                record.state = new_state;
            }
            (current, target) => {
                return Err(format!("ILLEGAL TRANSITION: {:?} -> {:?}", current, target));
            }
        }

        // Release pending risk exposure only on terminal states
        if new_state == OrderStatus::Executed || new_state == OrderStatus::Rejected {
            self.total_pending_exposure -= record.notional_exposure;
        }

        Ok(())
    }
}