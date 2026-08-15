use async_trait::async_trait;

#[derive(Debug)]
pub struct BrokerSubmissionIntent {
    pub idempotency_key: String,
    pub instrument: String,
    pub quantity: u64,
    // ...
}

#[derive(Debug)]
pub enum SubmissionOutcome {
    Accepted { broker_order_id: String },
    Rejected { reason: String },
    Unknown { reason: String }, // Timeouts, TCP Resets
}

#[derive(Debug)]
pub enum CancellationOutcome {
    Accepted,
    Rejected { reason: String },
    Unknown { reason: String },
}

#[derive(Debug)]
pub enum ReconciliationResult {
    ConfirmedFact(BrokerFact),
    NotObservedYet, // E.g., API returned "NotFound" or eventual-consistency lag
    Unavailable,    // API down
    Ambiguous,      // Conflicting data
}

#[derive(Debug)]
pub enum BrokerFact {
    Acknowledged { broker_order_id: String },
    Filled { broker_fill_id: String, filled_qty: u64, remaining_qty: u64 },
    Rejected { reason: String },
    Cancelled { remaining_qty: u64 },
}

#[async_trait]
pub trait BrokerConnector {
    /// Dispatches the initial intent to the exchange.
    async fn submit_order(&self, intent: BrokerSubmissionIntent) -> Result<SubmissionOutcome, String>;

    /// Issues a cancellation intent.
    async fn cancel_order(&self, broker_order_id: &str, idempotency_key: &str) -> Result<CancellationOutcome, String>;

    /// Polls or receives authoritative facts for a specific order.
    async fn reconcile_order(&self, broker_order_id: Option<&str>, idempotency_key: &str) -> Result<ReconciliationResult, String>;
}