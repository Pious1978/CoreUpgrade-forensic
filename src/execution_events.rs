use serde::{Deserialize, Serialize};
use crate::money::Money;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum GatewayIntent {
    OrderAdmitted {
        order_id: String,
        sequence_number: u64,
        request_nonce: String,
        certificate_generation: u64,
        instrument: String,
        requested_quantity: u64,
    },
    RiskReserved {
        order_id: String,
        notional_exposure: Money,
    },
    SubmissionStarted {
        order_id: String,
        idempotency_key: String,
    },
    CancelRequested {
        order_id: String,
        cancel_idempotency_key: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum GatewayUncertainty {
    SubmissionUnknown {
        order_id: String,
        reason: String,
    },
    CancelUnknown {
        order_id: String,
        reason: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum BrokerFact {
    BrokerAcknowledged {
        order_id: String,
        broker_order_id: String,
        requested_quantity: u64,
        original_exposure: Money,
    },
    FillReceived {
        order_id: String,
        broker_order_id: String,
        broker_fill_id: String,
        fill_quantity: u64,
        price: Money,
        remaining_quantity: u64,
    },
    BrokerRejected {
        order_id: String,
        reason: String,
    },
    CancelConfirmed {
        order_id: String,
        remaining_quantity: u64,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ExecutionEvent {
    Intent(GatewayIntent),
    Uncertainty(GatewayUncertainty),
    Fact(BrokerFact),
}

/// Unified commands issued by the scenario harness.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum GatewayCommand {
    Admit {
        order_id: u8,
        quantity: u64,
        exposure: u64,
    },
    Submit {
        order_id: u8,
    },
    Cancel {
        order_id: u8,
    },
}

/// Chaos/reference-layer authoritative broker facts.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum BrokerFactEvent {
    Accepted {
        order_id: u8,
        broker_order_id: String,
        requested_quantity: u64,
        original_exposure: Money,
    },
    Rejected {
        order_id: u8,
        reason: String,
    },
    Fill {
        order_id: u8,
        fill_id: String,
        quantity: u64,
        remaining: u64,
        price: Money,
    },
    CancelConfirmed {
        order_id: u8,
        remaining: u64,
    },
}