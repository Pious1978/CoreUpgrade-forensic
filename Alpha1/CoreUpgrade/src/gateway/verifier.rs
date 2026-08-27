// src/gateway/verifier.rs

use p384::ecdsa::{Signature, VerifyingKey};
use ecdsa::signature::hazmat::PrehashVerifier;
use serde_json::Value;
use sha2::{Digest, Sha384};

use crate::protocol::{UdsEnvelope, MAX_PAYLOAD_BYTES, ORDER_GATE_CONTEXT, PROTOCOL_VERSION};
use crate::replay_guard::ReplayGuard;
use crate::state_store::StateStore;
use crate::pki::ActiveCertificateState;

pub struct OrderVerifier;

impl OrderVerifier {
    pub fn verify_and_admit(
        raw_json_bytes: &[u8],
        state_store: &mut StateStore,
        certificate: &ActiveCertificateState,
    ) -> Result<Value, String> {

        // 1. HARD SIZE BOUNDARY
        if raw_json_bytes.len() > MAX_PAYLOAD_BYTES { return Err("REJECTED: Payload exceeds maximum size.".to_string()); }
        if raw_json_bytes.is_empty() { return Err("REJECTED: Empty payload.".to_string()); }

        // 2. PARSE ENVELOPE
        let envelope: UdsEnvelope = serde_json::from_slice(raw_json_bytes)
            .map_err(|e| format!("REJECTED: Malformed envelope: {}", e))?;
        let payload = &envelope.order_payload;
        if !payload.is_object() { return Err("REJECTED: Order payload must be a JSON object.".to_string()); }

        // 3. PROTOCOL VALIDATION
        let protocol = payload.get("protocol_version").and_then(Value::as_str).ok_or("REJECTED: Missing protocol_version")?;
        if protocol != PROTOCOL_VERSION { return Err("REJECTED: Unsupported protocol version.".to_string()); }

        let epoch = payload.get("epoch").and_then(Value::as_u64).ok_or("REJECTED: Missing/invalid epoch")?;
        let sequence = payload.get("sequence").and_then(Value::as_u64).ok_or("REJECTED: Missing/invalid sequence")?;
        let nonce = payload.get("nonce").and_then(Value::as_str).ok_or("REJECTED: Missing nonce")?;
        if nonce.is_empty() { return Err("REJECTED: Empty nonce.".to_string()); }

        // 4. NUMERIC SAFETY
        let quantity = payload.get("quantity").and_then(Value::as_f64).ok_or("REJECTED: Missing/invalid quantity")?;
        let price = payload.get("price").and_then(Value::as_f64).ok_or("REJECTED: Missing/invalid price")?;
        if !quantity.is_finite() || quantity < 0.0 || !price.is_finite() || price < 0.0 {
            return Err("REJECTED: Invalid numeric values.".to_string());
        }

        // 5. INDEPENDENT RFC8785 CANONICALIZATION
        let canonical_bytes = canonicaljson::to_string(payload)
            .map_err(|e| format!("REJECTED: RFC8785 canonicalization failed: {}", e))?.into_bytes();

        if canonical_bytes.len() > MAX_PAYLOAD_BYTES { return Err("REJECTED: Canonical payload exceeds size.".to_string()); }

        // 6. DOMAIN-SEPARATED SHA-384
        let mut hasher = Sha384::new();
        hasher.update(ORDER_GATE_CONTEXT);
        hasher.update(&canonical_bytes);
        let digest = hasher.finalize();

        // 7. TRUSTED KEY RESOLUTION
        // Key identity is strictly provided by the trusted PKI, NOT the UDS payload.
        let verifying_key = VerifyingKey::from_public_key_der(&certificate.leaf_public_key_der)
            .map_err(|_| "CRITICAL ERROR: Internal trusted DER public key invalid".to_string())?;

        let signature_bytes = hex::decode(&envelope.authorization.certificate_signature_hex)
            .map_err(|_| "REJECTED: Invalid signature hex encoding".to_string())?;

        let signature = Signature::from_der(&signature_bytes)
            .map_err(|_| "REJECTED: Invalid ECDSA signature DER format".to_string())?;

        // 8. ECDSA P-384 PREHASH VERIFICATION
        verifying_key.verify_prehash(&digest, &signature)
            .map_err(|_| "REJECTED: Cryptographic signature verification failed".to_string())?;

        // 9. REPLAY STATE VERIFICATION
        ReplayGuard::assert_admissible(state_store, epoch, sequence, nonce).map_err(|e| e.to_string())?;

        // 10. ATOMIC STATE COMMIT
        ReplayGuard::commit_reservation(state_store, sequence, nonce.to_string())
            .map_err(|e| format!("CRITICAL ERROR: State commit failed: {}", e))?;

        Ok(payload.clone())
    }
}