// src/gateway/pki.rs

use std::fs::File;
use std::io::Read;
use serde_json::json;
use p384::ecdsa::{Signature, VerifyingKey};
use ecdsa::signature::hazmat::PrehashVerifier;
use sha2::{Digest, Sha384};

const ROOT_CA_PATH: &str = "/etc/trading-engine/trust/root_ca.der";
const INTERMEDIATE_CA_PATH: &str = "/etc/trading-engine/trust/active_intermediate_ca.json";

// Cryptographic domain contexts identically matching StrictCryptographicEngine in Python
const INTERMEDIATE_CONTEXT: &[u8] = b"TRADING_ENGINE_INTERMEDIATE_CA_V1\0";
const LEAF_CONTEXT: &[u8] = b"TRADING_ENGINE_LEAF_KEY_V1\0";
const CERT_ASSERTION_CONTEXT: &[u8] = b"TRADING_ENGINE_CERTIFICATE_ASSERTION_V1\0";

#[derive(Clone, Debug)]
pub struct ActiveCertificateState {
    pub serial: String,
    pub leaf_public_key_der: Vec<u8>,

    pub allowed_strategy_hashes: Vec<String>,
    pub allowed_accounts: Vec<String>,

    pub max_order_notional: f64,
    pub max_velocity_1s: f64,

    pub created_at: f64,
    pub expires_at: f64,
    pub rotation_generation: u64,
}

pub struct PKIVerifier;

impl PKIVerifier {
    pub fn load_and_verify_active_certificate(
        cert_path: &str, 
        trusted_utc_time: f64
    ) -> Result<ActiveCertificateState, String> {
        
        // ------------------------------------------------------------
        // 1. LOAD TRUST ANCHORS AND FILES
        // ------------------------------------------------------------
        let root_ca_der = Self::read_file_bytes(ROOT_CA_PATH)?;
        let root_key = VerifyingKey::from_public_key_der(&root_ca_der)
            .map_err(|_| "CRITICAL ERROR: Invalid Root CA DER".to_string())?;

        let intermediate_json = Self::read_file_string(INTERMEDIATE_CA_PATH)?;
        let int_val: serde_json::Value = serde_json::from_str(&intermediate_json)
            .map_err(|e| format!("CRITICAL ERROR: Intermediate CA JSON invalid: {}", e))?;

        let cert_json = Self::read_file_string(cert_path)?;
        let cert_val: serde_json::Value = serde_json::from_str(&cert_json)
            .map_err(|e| format!("CRITICAL ERROR: Startup Cert JSON invalid: {}", e))?;

        // ------------------------------------------------------------
        // 2. VERIFY INTERMEDIATE CA (Signed by Root CA)
        // ------------------------------------------------------------
        let int_pub_hex = int_val["public_key_hex"].as_str().ok_or("Missing intermediate pub key")?;
        let int_sig_hex = int_val["signature_hex"].as_str().ok_or("Missing intermediate signature")?;
        let int_pub_der = hex::decode(int_pub_hex).map_err(|_| "Invalid intermediate hex encoding")?;
        
        let int_payload = json!({
            "key_id": int_val["key_id"],
            "public_key_hex": int_pub_hex,
            "generation": int_val.get("generation").unwrap_or(&json!(1)),
            "purpose": "TRADING_ENGINE_INTERMEDIATE_CA"
        });
        
        Self::verify_cryptographic_assertion(
            &root_key, 
            int_sig_hex, 
            &int_payload, 
            INTERMEDIATE_CONTEXT,
            "Intermediate CA"
        )?;

        let intermediate_key = VerifyingKey::from_public_key_der(&int_pub_der)
            .map_err(|_| "CRITICAL ERROR: Invalid Intermediate CA DER".to_string())?;

        // ------------------------------------------------------------
        // 3. VERIFY LEAF EXECUTION KEY (Signed by Intermediate CA)
        // ------------------------------------------------------------
        let leaf_pub_hex = cert_val["leaf_public_key_hex"].as_str().ok_or("Missing leaf pub key")?;
        let leaf_sig_hex = cert_val["leaf_signature_hex"].as_str().ok_or("Missing leaf signature")?;
        let leaf_pub_der = hex::decode(leaf_pub_hex).map_err(|_| "Invalid leaf hex encoding")?;

        let leaf_payload = json!({
            "public_key_hex": leaf_pub_hex,
            "authority_key_hex": int_pub_hex,
            "purpose": "TRADING_ENGINE_EXECUTION_KEY"
        });

        Self::verify_cryptographic_assertion(
            &intermediate_key, 
            leaf_sig_hex, 
            &leaf_payload, 
            LEAF_CONTEXT,
            "Leaf Execution Key"
        )?;

        // ------------------------------------------------------------
        // 4. VERIFY STARTUP CERTIFICATE (Signed by Leaf Execution Key)
        // ------------------------------------------------------------
        let cert_hash_hex = cert_val["certificate_hash_hex"].as_str().ok_or("Missing cert hash")?;
        let cert_sig_hex = cert_val["certificate_signature_hex"].as_str().ok_or("Missing cert signature")?;
        let cert_hash_bytes = hex::decode(cert_hash_hex).map_err(|_| "Invalid cert hash hex encoding")?;

        let leaf_key = VerifyingKey::from_public_key_der(&leaf_pub_der)
            .map_err(|_| "CRITICAL ERROR: Invalid Leaf Key DER".to_string())?;

        let mut hasher = Sha384::new();
        hasher.update(CERT_ASSERTION_CONTEXT);
        hasher.update(&cert_hash_bytes);
        let digest = hasher.finalize();

        let signature_bytes = hex::decode(cert_sig_hex).map_err(|_| "Invalid cert signature hex")?;
        let signature = Signature::from_der(&signature_bytes).map_err(|_| "Invalid signature format")?;

        leaf_key.verify_prehash(&digest, &signature)
            .map_err(|_| "CRITICAL ERROR: Startup Certificate assertion verification failed".to_string())?;

        // ------------------------------------------------------------
        // 5. VALIDATE POLICY WINDOW
        // ------------------------------------------------------------
        let created_at = cert_val["created_at"].as_f64().ok_or("Missing created_at")?;
        let expires_at = cert_val["expires_at"].as_f64().ok_or("Missing expires_at")?;

        if trusted_utc_time < created_at { 
            return Err("CRITICAL ERROR: Certificate issued in the future".into()); 
        }
        if trusted_utc_time > expires_at { 
            return Err("CRITICAL ERROR: Certificate expired".into()); 
        }

        // ------------------------------------------------------------
        // 6. BUILD IMMUTABLE TRUSTED STATE
        // ------------------------------------------------------------
        let parse_vec = |key: &str| -> Result<Vec<String>, String> {
            cert_val[key].as_array()
                .ok_or_else(|| format!("Missing {}", key))?
                .iter()
                .map(|v| v.as_str().map(String::from).ok_or_else(|| "Invalid array string".into()))
                .collect()
        };

        Ok(ActiveCertificateState {
            serial: cert_val["serial"].as_str().unwrap_or("").to_string(),
            leaf_public_key_der: leaf_pub_der,
            allowed_strategy_hashes: parse_vec("allowed_strategy_hashes")?,
            allowed_accounts: parse_vec("allowed_accounts")?,
            max_order_notional: cert_val["max_order_notional"].as_f64().unwrap_or(0.0),
            max_velocity_1s: cert_val["max_velocity_1s"].as_f64().unwrap_or(0.0),
            created_at,
            expires_at,
            rotation_generation: cert_val["rotation_generation"].as_u64().unwrap_or(0),
        })
    }

    fn verify_cryptographic_assertion(
        key: &VerifyingKey, 
        sig_hex: &str, 
        payload: &serde_json::Value, 
        context: &[u8],
        label: &str
    ) -> Result<(), String> {
        let canonical_bytes = canonicaljson::to_string(payload)
            .map_err(|e| format!("CRITICAL ERROR: {} canonicalization failed: {}", label, e))?.into_bytes();

        let mut hasher = Sha384::new();
        hasher.update(context);
        hasher.update(&canonical_bytes);
        let digest = hasher.finalize();

        let sig_bytes = hex::decode(sig_hex).map_err(|_| format!("Invalid {} signature hex", label))?;
        let signature = Signature::from_der(&sig_bytes).map_err(|_| format!("Invalid {} signature DER", label))?;

        key.verify_prehash(&digest, &signature)
            .map_err(|_| format!("CRITICAL ERROR: {} signature verification failed", label))
    }

    fn read_file_bytes(path: &str) -> Result<Vec<u8>, String> {
        let mut f = File::open(path).map_err(|e| format!("Failed to read {}: {}", path, e))?;
        let mut buf = Vec::new();
        f.read_to_end(&mut buf).map_err(|e| e.to_string())?;
        Ok(buf)
    }

    fn read_file_string(path: &str) -> Result<String, String> {
        let mut f = File::open(path).map_err(|e| format!("Failed to read {}: {}", path, e))?;
        let mut buf = String::new();
        f.read_to_string(&mut buf).map_err(|e| e.to_string())?;
        Ok(buf)
    }
}