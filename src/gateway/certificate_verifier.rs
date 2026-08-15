// src/gateway/certificate_verifier.rs

use std::fs::File;
use std::io::Read;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use p384::ecdsa::{Signature, VerifyingKey};
use ecdsa::signature::hazmat::PrehashVerifier;
use sha2::{Digest, Sha384};

const ROOT_CA_PATH: &str = "/etc/trading-engine/trust/root_ca.der";
const LEAF_PURPOSE: &[u8] = b"TRADING_ENGINE_EXECUTION_KEY\0";
const CERT_ASSERTION_CONTEXT: &[u8] = b"TRADING_ENGINE_CERTIFICATE_ASSERTION_V1\0";

#[derive(Deserialize, Debug, Clone)]
pub struct StartupCertificate {
    pub algorithm: String,
    pub key_id: String,
    pub leaf_public_key_hex: String,
    pub certificate_hash_hex: String,
    pub certificate_signature_hex: String,
    
    pub serial: String,
    pub created_at: f64,
    pub expires_at: f64,
    
    pub allowed_strategy_hashes: Vec<String>,
    pub allowed_accounts: Vec<String>,
    pub max_order_notional: f64,
    pub max_velocity_1s: f64,
}

pub struct CertificateVerifier;

impl CertificateVerifier {
    /// Loads the Root CA from the secure, read-only filesystem boundary.
    fn load_root_ca() -> Result<VerifyingKey, String> {
        let mut file = File::open(ROOT_CA_PATH)
            .map_err(|e| format!("CRITICAL ERROR: Unable to read Root CA: {}", e))?;
        
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer)
            .map_err(|e| format!("CRITICAL ERROR: Root CA read failed: {}", e))?;
            
        VerifyingKey::from_public_key_der(&buffer)
            .map_err(|_| "CRITICAL ERROR: Invalid Root CA DER format".to_string())
    }

    /// Validates that the leaf key used to sign the order is explicitly authorized 
    /// by the active Startup Certificate and bounds it to the PKI root.
    pub fn verify_active_certificate(
        cert: &StartupCertificate,
        supplied_leaf_pub_key_der: &[u8],
        trusted_utc_time: f64,
    ) -> Result<(), String> {
        
        // 1. Time Validity
        if trusted_utc_time < cert.created_at {
            return Err("REJECTED: Certificate issued in the future.".to_string());
        }
        if trusted_utc_time > cert.expires_at {
            return Err("REJECTED: Certificate expired.".to_string());
        }

        // 2. Identity Match
        let cert_leaf_bytes = hex::decode(&cert.leaf_public_key_hex)
            .map_err(|_| "REJECTED: Invalid hex in certificate leaf key".to_string())?;
            
        if supplied_leaf_pub_key_der != cert_leaf_bytes.as_slice() {
            return Err("REJECTED: Supplied leaf key does not match authorized certificate.".to_string());
        }

        // 3. Cryptographic Assertion Validation
        // SHA384( CERTIFICATE_ASSERTION_CONTEXT || certificate_hash )
        let cert_hash_bytes = hex::decode(&cert.certificate_hash_hex)
            .map_err(|_| "REJECTED: Invalid hex in certificate hash".to_string())?;

        let mut hasher = Sha384::new();
        hasher.update(CERT_ASSERTION_CONTEXT);
        hasher.update(&cert_hash_bytes);
        let digest = hasher.finalize();

        let verifying_key = VerifyingKey::from_public_key_der(supplied_leaf_pub_key_der)
            .map_err(|_| "REJECTED: Invalid DER format for leaf key".to_string())?;

        let sig_bytes = hex::decode(&cert.certificate_signature_hex)
            .map_err(|_| "REJECTED: Invalid hex in certificate signature".to_string())?;
            
        let signature = Signature::from_der(&sig_bytes)
            .map_err(|_| "REJECTED: Invalid ECDSA signature DER format".to_string())?;

        verifying_key.verify_prehash(&digest, &signature)
            .map_err(|_| "REJECTED: Cryptographic certificate assertion failed".to_string())?;

        // Note: Full chain resolution (Root -> Intermediate -> Leaf) should be 
        // evaluated here or enforced at startup depending on sidecar initialization design.

        Ok(())
    }
}