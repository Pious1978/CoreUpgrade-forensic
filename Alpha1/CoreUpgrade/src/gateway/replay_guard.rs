use crate::state_store::StateStore;

pub struct ReplayGuard;

impl ReplayGuard {
    /// Validates replay and monotonicity constraints without mutating state.
    /// This ensures we don't consume a nonce if the signature later fails.
    pub fn assert_admissible(
        store: &StateStore,
        epoch: u64,
        sequence: u64,
        nonce: &str,
    ) -> Result<(), &'static str> {
        let state = store.get_state();

        if epoch != state.current_epoch {
            return Err("REJECTED: Epoch mismatch. Restart required.");
        }

        if sequence <= state.last_accepted_sequence {
            return Err("REJECTED: Sequence is not strictly monotonic.");
        }

        if nonce.len() != 32 {
            return Err("REJECTED: Invalid nonce length.");
        }

        if state.used_nonces.contains(nonce) {
            return Err("REJECTED: Nonce has already been consumed.");
        }

        Ok(())
    }

    /// Atomically commits the sequence and nonce.
    /// Must only be called AFTER all cryptographic and risk checks pass.
    pub fn commit_reservation(
        store: &mut StateStore,
        sequence: u64,
        nonce: String,
    ) -> Result<(), String> {
        store.update_state(|state| {
            state.last_accepted_sequence = sequence;
            state.used_nonces.insert(nonce);
        })
    }
}