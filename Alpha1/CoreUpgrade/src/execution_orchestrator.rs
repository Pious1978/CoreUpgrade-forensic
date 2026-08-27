use std::collections::{HashMap, HashSet};
use serde::{Deserialize, Serialize};
use crate::execution_events::{ExecutionEvent, GatewayIntent, GatewayUncertainty, BrokerFact};
use crate::journal::DurableJournal;
use crate::money::Money;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderStatus {
    Admitted, 
    RiskReserved, 
    SubmissionPending, 
    Unknown, 
    Acknowledged, 
    PartiallyFilled, 
    CancelPending,
    CancelUnknown,
    Filled, 
    BrokerRejected, 
    Cancelled,
}

impl OrderStatus {
    pub fn is_terminal(&self) -> bool {
        matches!(
            self, 
            OrderStatus::Filled 
                | OrderStatus::BrokerRejected 
                | OrderStatus::Cancelled
        )
    }
}

#[derive(Clone, Serialize, Deserialize)]
pub struct ExecutionRecord {
    pub order_id: String,
    pub state: OrderStatus,
    pub sequence_number: u64,
    pub request_nonce: String,
    pub certificate_generation: u64,
    pub instrument: String,
    pub requested_quantity: u64,
    pub idempotency_key: Option<String>,
    pub cancel_idempotency_key: Option<String>,
    pub broker_order_id: Option<String>,
    pub original_exposure: Option<Money>,
    pub cumulative_released_exposure: Option<Money>,
    pub cumulative_filled_quantity: u64,
    pub observed_fills: HashSet<String>, 
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EconomicSnapshot {
    pub state: String,
    pub requested_qty: u64,
    pub filled_qty: u64,
    pub remaining_qty: u64,
    pub original_exposure_units: i128,
    pub released_exposure_units: i128,
    pub reserved_exposure_units: i128,
    pub has_broker_identity: bool,
    pub observed_fills: HashSet<String>,
}

pub trait EconomicView {
    fn projected_snapshot(&self) -> HashMap<String, EconomicSnapshot>;
}

#[derive(Clone, Serialize, Deserialize)]
pub struct FillIdentityRecord {
    pub order_id: String,
    pub broker_order_id: String,
    pub quantity: u64,
    pub remaining_quantity: u64,
    pub price: Money,
}

pub struct ExecutionOrchestrator {
    active_orders: HashMap<String, ExecutionRecord>,
    journal: DurableJournal,
    global_fill_payloads: HashMap<String, FillIdentityRecord>,
    global_broker_orders: HashMap<String, String>,
}

impl EconomicView for ExecutionOrchestrator {
    fn projected_snapshot(&self) -> HashMap<String, EconomicSnapshot> {
        self.active_orders.iter().map(|(id, rec)| {
            let original = rec.original_exposure.clone().unwrap_or_else(|| Money::zero("USD", 4));
            let released = rec.cumulative_released_exposure.clone().unwrap_or_else(|| Money::zero(&original.currency.0, original.scale));
            
            let reserved_units = original.units
                .checked_sub(released.units)
                .expect("FATAL: Reserved exposure underflow");

            let state_str = match rec.state {
                OrderStatus::Admitted => "Admitted",
                OrderStatus::RiskReserved => "RiskReserved",
                OrderStatus::SubmissionPending => "SubmissionPending",
                OrderStatus::Unknown => "Unknown",
                OrderStatus::Acknowledged => "Acknowledged",
                OrderStatus::PartiallyFilled => "PartiallyFilled",
                OrderStatus::CancelPending => "CancelPending",
                OrderStatus::CancelUnknown => "CancelUnknown",
                OrderStatus::Filled => "Filled",
                OrderStatus::BrokerRejected => "BrokerRejected",
                OrderStatus::Cancelled => "Cancelled",
            }.to_string();

            (
                id.clone(),
                EconomicSnapshot {
                    state: state_str,
                    requested_qty: rec.requested_quantity,
                    filled_qty: rec.cumulative_filled_quantity,
                    remaining_qty: rec.requested_quantity
                        .checked_sub(rec.cumulative_filled_quantity)
                        .expect("FATAL: execution quantity underflow"),
                    original_exposure_units: original.units,
                    released_exposure_units: released.units,
                    reserved_exposure_units: reserved_units,
                    has_broker_identity: rec.broker_order_id.is_some(),
                    observed_fills: rec.observed_fills.clone(),
                },
            )
        }).collect()
    }
}

impl ExecutionOrchestrator {
    pub fn recover_and_start(mut journal: DurableJournal) -> Result<Self, String> {
        let events = journal.recover_and_verify()?;
        let mut orchestrator = Self {
            active_orders: HashMap::new(),
            journal,
            global_fill_payloads: HashMap::new(),
            global_broker_orders: HashMap::new(),
        };
        
        for event in events {
            orchestrator.apply_event_internal(&event, true)?;
        }
        
        Ok(orchestrator)
    }

    pub fn process_event_transaction(
        &mut self,
        events: Vec<ExecutionEvent>,
        timestamp_ns: i128,
    ) -> Result<(), String> {
        if events.is_empty() {
            return Err("Cannot commit an empty execution transaction".into());
        }

        let mut candidate_orders = self.active_orders.clone();
        let mut candidate_fills = self.global_fill_payloads.clone();
        let mut candidate_broker_orders = self.global_broker_orders.clone();

        for event in &events {
            Self::validate_and_apply_to_maps(
                event,
                &mut candidate_orders,
                &mut candidate_fills,
                &mut candidate_broker_orders,
                false,
            )?;
        }

        self.journal.commit_transaction(events, timestamp_ns)?;

        self.active_orders = candidate_orders;
        self.global_fill_payloads = candidate_fills;
        self.global_broker_orders = candidate_broker_orders;
        
        Ok(())
    }

    pub fn process_broker_fact(
        &mut self,
        fact: ExecutionEvent,
        timestamp_ns: i128,
    ) -> Result<(), String> {
        self.process_event_transaction(vec![fact], timestamp_ns)
    }

    pub fn mark_submission_started(
        &mut self,
        order_id: &str,
        idempotency_key: &str,
        timestamp_ns: i128,
    ) -> Result<(), String> {
        if order_id.trim().is_empty() || idempotency_key.trim().is_empty() {
            return Err("FATAL: Empty order_id or idempotency_key".into());
        }

        let event = ExecutionEvent::Intent(GatewayIntent::SubmissionStarted {
            order_id: order_id.to_string(),
            idempotency_key: idempotency_key.to_string(),
        });

        self.process_event_transaction(vec![event], timestamp_ns)
    }

    pub fn get_unknown_orders(&self) -> Vec<String> {
        self.active_orders
            .iter()
            .filter(|(_, rec)| {
                matches!(
                    rec.state,
                    OrderStatus::SubmissionPending
                        | OrderStatus::Unknown
                        | OrderStatus::CancelUnknown
                )
            })
            .map(|(id, _)| id.clone())
            .collect()
    }

    fn apply_event_internal(
        &mut self,
        event: &ExecutionEvent,
        is_recovery: bool,
    ) -> Result<(), String> {
        Self::validate_and_apply_to_maps(
            event,
            &mut self.active_orders,
            &mut self.global_fill_payloads,
            &mut self.global_broker_orders,
            is_recovery,
        )
    }

    fn validate_and_apply_to_maps(
        event: &ExecutionEvent,
        orders: &mut HashMap<String, ExecutionRecord>,
        fill_payloads: &mut HashMap<String, FillIdentityRecord>,
        broker_orders: &mut HashMap<String, String>,
        is_recovery: bool,
    ) -> Result<(), String> {
        match event {
            ExecutionEvent::Intent(
                GatewayIntent::OrderAdmitted {
                    order_id,
                    sequence_number,
                    request_nonce,
                    certificate_generation,
                    instrument,
                    requested_quantity,
                },
            ) => {
                if order_id.trim().is_empty() || request_nonce.trim().is_empty() || instrument.trim().is_empty() {
                    return Err("FATAL: Empty admission identifiers".into());
                }
                if *requested_quantity == 0 {
                    return Err("FATAL: requested quantity must be > 0".into());
                }

                if let Some(existing) = orders.get(order_id) {
                    if existing.sequence_number != *sequence_number
                        || existing.request_nonce != *request_nonce
                        || existing.certificate_generation != *certificate_generation
                        || existing.instrument != *instrument
                        || existing.requested_quantity != *requested_quantity
                    {
                        return Err(format!(
                            "FATAL: Duplicate order_id {} with contradictory immutable admission parameters",
                            order_id
                        ));
                    }

                    if !is_recovery {
                        return Err(format!("Duplicate order_id: {}", order_id));
                    }
                    return Ok(());
                }

                orders.insert(
                    order_id.clone(),
                    ExecutionRecord {
                        order_id: order_id.clone(),
                        state: OrderStatus::Admitted,
                        sequence_number: *sequence_number,
                        request_nonce: request_nonce.clone(),
                        certificate_generation: *certificate_generation,
                        instrument: instrument.clone(),
                        requested_quantity: *requested_quantity,
                        idempotency_key: None,
                        cancel_idempotency_key: None,
                        broker_order_id: None,
                        original_exposure: None,
                        cumulative_released_exposure: None,
                        cumulative_filled_quantity: 0,
                        observed_fills: HashSet::new(),
                    },
                );
            }
            ExecutionEvent::Intent(
                GatewayIntent::RiskReserved {
                    order_id,
                    notional_exposure,
                },
            ) => {
                if notional_exposure.units < 0 {
                    return Err("FATAL: Negative exposure is invalid".into());
                }

                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                if rec.state != OrderStatus::Admitted {
                    return Err(format!("Illegal transition to RiskReserved from {:?}", rec.state));
                }

                rec.state = OrderStatus::RiskReserved;
                rec.original_exposure = Some(notional_exposure.clone());
                rec.cumulative_released_exposure = Some(Money::zero(
                    &notional_exposure.currency.0,
                    notional_exposure.scale,
                ));
            }
            ExecutionEvent::Intent(
                GatewayIntent::SubmissionStarted {
                    order_id,
                    idempotency_key,
                },
            ) => {
                if idempotency_key.trim().is_empty() {
                    return Err("FATAL: Empty submission idempotency_key".into());
                }

                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                match rec.state {
                    OrderStatus::RiskReserved => {
                        rec.state = OrderStatus::SubmissionPending;
                        rec.idempotency_key = Some(idempotency_key.clone());
                    }
                    _ => {
                        return Err(format!("Illegal transition to SubmissionPending from {:?}", rec.state));
                    }
                }
            }
            ExecutionEvent::Intent(
                GatewayIntent::CancelRequested {
                    order_id,
                    cancel_idempotency_key,
                },
            ) => {
                if cancel_idempotency_key.trim().is_empty() {
                    return Err("FATAL: Empty cancel_idempotency_key".into());
                }

                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                match rec.state {
                    OrderStatus::Acknowledged | OrderStatus::PartiallyFilled => {
                        if let Some(existing) = &rec.cancel_idempotency_key {
                            if existing != cancel_idempotency_key {
                                return Err("FATAL: Cancellation idempotency key mutation".into());
                            }
                        } else {
                            rec.cancel_idempotency_key = Some(cancel_idempotency_key.clone());
                        }
                        rec.state = OrderStatus::CancelPending;
                    }
                    OrderStatus::CancelPending | OrderStatus::CancelUnknown => {
                        if let Some(existing) = &rec.cancel_idempotency_key {
                            if existing != cancel_idempotency_key {
                                return Err("FATAL: Cancellation idempotency key mutation".into());
                            }
                        } else {
                            return Err("FATAL: Existing cancellation state has no cancellation identity".into());
                        }
                    }
                    _ => {
                        return Err(format!("Illegal transition to CancelPending from {:?}", rec.state));
                    }
                }
            }
            ExecutionEvent::Uncertainty(
                GatewayUncertainty::SubmissionUnknown { order_id, .. },
            ) => {
                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                match rec.state {
                    OrderStatus::SubmissionPending | OrderStatus::Unknown => {
                        rec.state = OrderStatus::Unknown;
                    }
                    _ => {
                        return Err(format!("Illegal transition to Unknown from {:?}", rec.state));
                    }
                }
            }
            ExecutionEvent::Uncertainty(
                GatewayUncertainty::CancelUnknown { order_id, .. },
            ) => {
                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                match rec.state {
                    OrderStatus::CancelPending | OrderStatus::CancelUnknown => {
                        rec.state = OrderStatus::CancelUnknown;
                    }
                    _ => {
                        return Err(format!("Illegal transition to CancelUnknown from {:?}", rec.state));
                    }
                }
            }
            ExecutionEvent::Fact(
                BrokerFact::BrokerAcknowledged {
                    order_id,
                    broker_order_id,
                    requested_quantity,
                    original_exposure,
                },
            ) => {
                if broker_order_id.trim().is_empty() {
                    return Err("FATAL: Empty broker_order_id".into());
                }

                if let Some(existing_owner) = broker_orders.get(broker_order_id) {
                    if existing_owner != order_id {
                        return Err(format!(
                            "FATAL: broker_order_id {} already belongs to order {}",
                            broker_order_id, existing_owner
                        ));
                    }
                }

                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                // Production verification of authoritative economics against admission/reservation
                if rec.requested_quantity != *requested_quantity {
                    return Err("FATAL: Broker acknowledged requested_quantity contradicts admission record".into());
                }
                if let Some(original) = &rec.original_exposure {
                    if original != original_exposure {
                        return Err("FATAL: Broker acknowledged original_exposure contradicts risk reservation".into());
                    }
                }

                match rec.state {
                    OrderStatus::SubmissionPending | OrderStatus::Unknown => {
                        if let Some(existing) = &rec.broker_order_id {
                            if existing != broker_order_id {
                                return Err("FATAL: Broker order identity mutation mismatch".into());
                            }
                        } else {
                            rec.broker_order_id = Some(broker_order_id.clone());
                            broker_orders.insert(broker_order_id.clone(), order_id.clone());
                        }
                        rec.state = OrderStatus::Acknowledged;
                    }
                    OrderStatus::Acknowledged
                    | OrderStatus::PartiallyFilled
                    | OrderStatus::CancelPending
                    | OrderStatus::CancelUnknown => {
                        let existing = rec.broker_order_id.as_ref()
                            .ok_or("FATAL: Existing broker state has no broker identity")?;
                        if existing != broker_order_id {
                            return Err("FATAL: Broker order identity mutation mismatch".into());
                        }
                    }
                    _ => {
                        return Err(format!("Illegal broker acknowledgement from {:?}", rec.state));
                    }
                }
            }
            ExecutionEvent::Fact(
                BrokerFact::FillReceived {
                    order_id,
                    broker_order_id,
                    broker_fill_id,
                    fill_quantity,
                    price,
                    remaining_quantity,
                },
            ) => {
                if broker_order_id.trim().is_empty() || broker_fill_id.trim().is_empty() {
                    return Err("FATAL: Empty fill identifiers".into());
                }

                if let Some(existing) = fill_payloads.get(broker_fill_id) {
                    if existing.order_id != *order_id
                        || existing.broker_order_id != *broker_order_id
                        || existing.quantity != *fill_quantity
                        || existing.remaining_quantity != *remaining_quantity
                        || existing.price != *price
                    {
                        return Err(format!(
                            "FATAL: broker_fill_id {} reused with contradictory payload",
                            broker_fill_id
                        ));
                    }
                    return Ok(());
                }

                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                if rec.state.is_terminal() {
                    return Err("FATAL: New fill received for terminal order".into());
                }

                let authoritative_broker_id = rec.broker_order_id.as_ref()
                    .ok_or("FATAL: Fill received without authoritative broker identity")?;

                if authoritative_broker_id != broker_order_id {
                    return Err("FATAL: Fill broker_order_id contradicts execution record".into());
                }

                if *fill_quantity == 0 {
                    return Err("FATAL: Fill quantity must be > 0".into());
                }

                let original = rec.original_exposure.as_ref()
                    .ok_or("FATAL: Missing original exposure")?;

                if price.currency != original.currency || price.scale != original.scale {
                    return Err("FATAL: Fill price currency/scale contradicts order exposure".into());
                }

                let new_filled = rec.cumulative_filled_quantity.checked_add(*fill_quantity)
                    .ok_or("FATAL: Fill quantity overflow")?;

                if new_filled > rec.requested_quantity {
                    return Err("FATAL: Cumulative fills exceed requested quantity".into());
                }

                let expected_remaining = rec.requested_quantity
                    .checked_sub(new_filled)
                    .ok_or("FATAL: Remaining quantity underflow")?;

                if expected_remaining != *remaining_quantity {
                    return Err("FATAL: Fill remaining quantity contradicts gateway arithmetic".into());
                }

                rec.cumulative_filled_quantity = new_filled;

                fill_payloads.insert(
                    broker_fill_id.clone(),
                    FillIdentityRecord {
                        order_id: order_id.clone(),
                        broker_order_id: broker_order_id.clone(),
                        quantity: *fill_quantity,
                        remaining_quantity: *remaining_quantity,
                        price: price.clone(),
                    },
                );

                rec.observed_fills.insert(broker_fill_id.clone());

                let cumulative_release_units = original.units
                    .checked_mul(rec.cumulative_filled_quantity as i128)
                    .ok_or("FATAL: Exposure release multiplication overflow")?
                    / rec.requested_quantity as i128;

                if let Some(released) = &mut rec.cumulative_released_exposure {
                    released.units = cumulative_release_units;
                }

                rec.state = if expected_remaining == 0 {
                    OrderStatus::Filled
                } else {
                    OrderStatus::PartiallyFilled
                };
            }
            ExecutionEvent::Fact(
                BrokerFact::BrokerRejected { order_id, .. },
            ) => {
                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                if rec.state.is_terminal() {
                    return Err("FATAL: Rejection received for terminal order".into());
                }

                match rec.state {
                    OrderStatus::SubmissionPending | OrderStatus::Unknown | OrderStatus::Acknowledged => {
                        rec.state = OrderStatus::BrokerRejected;
                        if let (Some(original), Some(released)) = (&rec.original_exposure, &mut rec.cumulative_released_exposure) {
                            released.units = original.units;
                        }
                    }
                    _ => {
                        return Err(format!("Illegal transition to BrokerRejected from {:?}", rec.state));
                    }
                }
            }
            ExecutionEvent::Fact(
                BrokerFact::CancelConfirmed {
                    order_id,
                    remaining_quantity,
                },
            ) => {
                let rec = orders.get_mut(order_id)
                    .ok_or_else(|| format!("Order not found: {}", order_id))?;

                if rec.state.is_terminal() {
                    return Err("FATAL: Cancellation confirmation received for terminal order".into());
                }

                match rec.state {
                    OrderStatus::Acknowledged
                    | OrderStatus::PartiallyFilled
                    | OrderStatus::CancelPending
                    | OrderStatus::CancelUnknown => {}
                    _ => {
                        return Err(format!("Illegal transition to Cancelled from {:?}", rec.state));
                    }
                }

                let expected_remaining = rec.requested_quantity
                    .checked_sub(rec.cumulative_filled_quantity)
                    .ok_or("FATAL: Remaining quantity underflow")?;

                if expected_remaining != *remaining_quantity {
                    return Err("FATAL: Cancellation remaining quantity contradicts gateway arithmetic".into());
                }

                rec.state = OrderStatus::Cancelled;

                if let (Some(original), Some(released)) = (&rec.original_exposure, &mut rec.cumulative_released_exposure) {
                    released.units = original.units;
                }
            }
        }

        Ok(())
    }
}