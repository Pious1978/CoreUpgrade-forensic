/// Institutional Certificate Lifecycle Manager
///
/// Security objectives:
/// - Provide O(1) lock-free certificate state access for the execution hot path.
/// - Serialize administrative certificate rotations to prevent race conditions.
/// - Enforce strictly monotonic generation rotation (rollback protection).
/// - Enforce Time-of-Check to Time-of-Use (TOCTOU) safety during concurrent rotations.
///
/// Concurrency Model: RCU (Read-Copy-Update)
/// Execution threads perform wait-free pointer reads via `ArcSwap`.
/// Rotation threads perform expensive cryptographic PKI verification off-lock, 
/// acquire a serialization mutex, verify generation invariants against the 
/// absolute latest state, and perform an atomic pointer swap.

use std::sync::Arc;
use arc_swap::ArcSwap;
use tokio::sync::Mutex;

use crate::pki::{PKIVerifier, ActiveCertificateState};
use crate::time::NetworkSynchronizedTimeProvider;

const STARTUP_CERT_PATH: &str = "/etc/trading-engine/trust/active_startup_certificate.json";

pub struct CertificateManager {
    // Lock-free read access for the execution hot path.
    active_state: ArcSwap<ActiveCertificateState>,
    
    // Dedicated lock to strictly serialize concurrent administrative rotation requests.
    // This prevents TOCTOU races where two concurrent rotations bypass generation checks.
    rotation_lock: Mutex<()>,
}

impl CertificateManager {
    /// Initializes the manager at boot.
    /// Fails closed (halts startup) if the active certificate is invalid, expired, 
    /// or fails PKI cryptographic verification.
    pub fn load_initial() -> Result<Self, String> {
        let trusted_time = NetworkSynchronizedTimeProvider::get_trusted_utc_time()?;
        
        let initial_state = PKIVerifier::load_and_verify_active_certificate(
            STARTUP_CERT_PATH, 
            trusted_time
        )?;

        Ok(CertificateManager {
            active_state: ArcSwap::from_pointee(initial_state),
            rotation_lock: Mutex::new(()),
        })
    }

    /// O(1) lock-free read for the execution hot path.
    /// Returns an immutable, reference-counted snapshot of the active certificate.
    pub fn get_active_certificate(&self) -> Arc<ActiveCertificateState> {
        self.active_state.load().clone()
    }

    /// Executed via administrative signal or dedicated rotation API.
    /// Strictly verifies the complete PKI chain of the new certificate before 
    /// applying the atomic state mutation.
    pub async fn rotate_certificate(&self, new_cert_path: &str) -> Result<(), String> {
        // 1. Obtain trusted network-anchored time
        let trusted_time = NetworkSynchronizedTimeProvider::get_trusted_utc_time()?;

        // 2. Expensive cryptographic validation occurs OFF the lock.
        // This ensures the execution gateway remains highly responsive while 
        // evaluating the new PKI chain.
        let new_state = PKIVerifier::load_and_verify_active_certificate(
            new_cert_path, 
            trusted_time
        )?;

        // 3. Serialize mutations
        let _guard = self.rotation_lock.lock().await;

        // 4. Re-read current state strictly under the rotation lock (TOCTOU protection).
        let current = self.active_state.load();

        // 5. Generation Rollback Protection
        if new_state.rotation_generation <= current.rotation_generation {
            return Err(format!(
                "CRITICAL ERROR: Generation rollback detected. New generation ({}) must be > current ({}).",
                new_state.rotation_generation, current.rotation_generation
            ));
        }

        // 6. Validity window continuity check
        if new_state.expires_at <= current.expires_at {
            return Err(
                "CRITICAL ERROR: New certificate does not extend certificate validity."
                .to_string()
            );
        }
        
        let new_generation = new_state.rotation_generation;

        // 7. Single atomic state transition via RCU pointer swap
        self.active_state.store(Arc::new(new_state));

        // Note: _guard is automatically dropped here, releasing the rotation_lock.
        
        println!(
            "SUCCESS: Execution certificate atomically rotated to generation {}.", 
            new_generation
        );

        Ok(())
    }
}