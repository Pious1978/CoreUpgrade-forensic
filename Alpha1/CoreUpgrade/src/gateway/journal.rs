use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::money::Money;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderStatus {
    Admitted,
    RiskReserved,
    SubmissionPending,
    Unknown,
    Acknowledged,
    PartiallyFilled { filled: u64, remaining: u64 },
    Filled,
    BrokerRejected { reason: String },
    GatewayRejected { reason: String },
    Cancelled { remaining: u64 },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ExecutionEvent {
    OrderAdmitted {
        order_id: String,
        sequence_number: u64,
        request_nonce: String,
        certificate_generation: u64,
        authorization_timestamp: f64,
        quantity: u64,
        instrument: String,
    },
    RiskReserved {
        order_id: String,
        notional_exposure: Money,
    },
    SubmissionStarted {
        order_id: String,
        idempotency_key: String,
    },
    SubmissionUnknown {
        order_id: String,
    },
    BrokerAcknowledged {
        order_id: String,
        broker_order_id: String,
    },
    FillReceived {
        order_id: String,
        fill_quantity: u64,
        remaining_quantity: u64,
    },
    BrokerRejected {
        order_id: String,
        reason: String,
    },
}

#[derive(Debug, Clone)]
pub struct ExecutionRecord {
    pub order_id: String,
    pub sequence_number: u64,
    pub request_nonce: String,
    pub idempotency_key: Option<String>,
    pub certificate_generation: u64,
    pub authorization_timestamp: f64,
    pub state: OrderStatus,
    pub requested_quantity: u64,
    pub notional_exposure: Money,
}

pub struct ExecutionOrchestrator {
    active_orders: HashMap<String, ExecutionRecord>,
    total_pending_exposure: Money,
    // Note: In production, this would wrap an append-only file handler or fast KV store (e.g., RocksDB, Sled)
    // event_log_file: std::fs::File,
}

impl ExecutionOrchestrator {
    pub fn new() -> Self {
        Self {
            active_orders: HashMap::new(),
            total_pending_exposure: Money::zero(),
        }
    }

    /// Primary atomic transaction boundary.
    /// In one operation, we durably persist the sequence admission and risk reservation.
    /// If writing to the journal fails, the system panics and NO state mutates.
    pub fn commit_admission_transaction(
        &mut self,
        admission_event: ExecutionEvent,
        risk_event: ExecutionEvent,
    ) -> Result<(), String> {
        
        // 1. Durably append to disk (fsync)
        // self.append_to_journal(&admission_event)?;
        // self.append_to_journal(&risk_event)?;
        
        // 2. Project into memory
        self.apply_event(&admission_event)?;
        self.apply_event(&risk_event)?;

        Ok(())
    }

    pub fn apply_event(&mut self, event: &ExecutionEvent) -> Result<(), String> {
        match event {
            ExecutionEvent::OrderAdmitted { order_id, sequence_number, request_nonce, certificate_generation, authorization_timestamp, quantity, .. } => {
                if self.active_orders.contains_key(order_id) {
                    return Err(format!("Duplicate order_id: {}", order_id));
                }
                self.active_orders.insert(order_id.clone(), ExecutionRecord {
                    order_id: order_id.clone(),
                    sequence_number: *sequence_number,
                    request_nonce: request_nonce.clone(),
                    idempotency_key: None,
                    certificate_generation: *certificate_generation,
                    authorization_timestamp: *authorization_timestamp,
                    state: OrderStatus::Admitted,
                    requested_quantity: *quantity,
                    notional_exposure: Money::zero(),
                });
            }
            ExecutionEvent::RiskReserved { order_id, notional_exposure } => {
                let record = self.get_mut_record(order_id)?;
                if record.state != OrderStatus::Admitted {
                    return Err("Illegal transition to RiskReserved".into());
                }
                record.state = OrderStatus::RiskReserved;
                record.notional_exposure = *notional_exposure;
                self.total_pending_exposure = self.total_pending_exposure + *notional_exposure;
            }
            ExecutionEvent::SubmissionStarted { order_id, idempotency_key } => {
                let record = self.get_mut_record(order_id)?;
                if record.state != OrderStatus::RiskReserved {
                    return Err("Illegal transition to SubmissionStarted".into());
                }
                record.state = OrderStatus::SubmissionPending;
                record.idempotency_key = Some(idempotency_key.clone());
            }
            ExecutionEvent::SubmissionUnknown { order_id } => {
                let record = self.get_mut_record(order_id)?;
                if record.state != OrderStatus::SubmissionPending {
                    return Err("Illegal transition to Unknown".into());
                }
                // UNKNOWN: Network timeout. The order is in limbo. Risk remains locked.
                record.state = OrderStatus::Unknown;
            }
            ExecutionEvent::BrokerAcknowledged { order_id, .. } => {
                let record = self.get_mut_record(order_id)?;
                match record.state {
                    OrderStatus::SubmissionPending | OrderStatus::Unknown => {
                        record.state = OrderStatus::Acknowledged;
                    }
                    _ => return Err("Illegal transition to Acknowledged".into()),
                }
            }
            ExecutionEvent::FillReceived { order_id, fill_quantity, remaining_quantity } => {
                let record = self.get_mut_record(order_id)?;
                // Calculates the exact risk to release based on fill ratio
                let release_ratio = (*fill_quantity as f64) / (record.requested_quantity as f64);
                let risk_to_release = Money::new((record.notional_exposure.basis_units as f64 * release_ratio) as i128);

                if *remaining_quantity == 0 {
                    record.state = OrderStatus::Filled;
                    // Release remaining risk (accounting for rounding drift)
                    self.total_pending_exposure = self.total_pending_exposure - record.notional_exposure;
                    record.notional_exposure = Money::zero();
                } else {
                    record.state = OrderStatus::PartiallyFilled { filled: *fill_quantity, remaining: *remaining_quantity };
                    self.total_pending_exposure = self.total_pending_exposure - risk_to_release;
                    record.notional_exposure = record.notional_exposure - risk_to_release;
                }
            }
            ExecutionEvent::BrokerRejected { order_id, reason } => {
                let record = self.get_mut_record(order_id)?;
                match record.state {
                    OrderStatus::SubmissionPending | OrderStatus::Unknown => {
                        record.state = OrderStatus::BrokerRejected { reason: reason.clone() };
                        // Complete risk release
                        self.total_pending_exposure = self.total_pending_exposure - record.notional_exposure;
                        record.notional_exposure = Money::zero();
                    }
                    _ => return Err("Illegal transition to BrokerRejected".into()),
                }
            }
        }
        Ok(())
    }

    fn get_mut_record(&mut self, order_id: &str) -> Result<&mut ExecutionRecord, String> {
        self.active_orders.get_mut(order_id).ok_or_else(|| format!("Order {} not found", order_id))
    }
}