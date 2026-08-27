// src/gateway/protocol.rs

use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const MAX_PAYLOAD_BYTES: usize = 4096;
pub const ORDER_GATE_CONTEXT: &[u8] = b"TRADING_ENGINE_ORDER_GATE_V1\0";
pub const PROTOCOL_VERSION: &str = "ORDER_GATE_V1";

#[derive(Deserialize, Debug)]
pub struct AuthorizationMetadata {
    // The sidecar derives the verifying key from its own PKI state.
    pub certificate_signature_hex: String,
}

#[derive(Deserialize, Debug)]
pub struct UdsEnvelope {
    pub order_payload: Value,
    pub authorization: AuthorizationMetadata,
}

#[derive(Serialize, Debug)]
pub struct GatewayResponse {
    pub status: String,
    pub reason: Option<String>,
}