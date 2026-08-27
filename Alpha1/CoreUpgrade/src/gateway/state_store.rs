use std::collections::HashSet;
use std::fs::File;
use std::io::{Read, Write};
use std::path::Path;
use serde::{Deserialize, Serialize};
use tempfile::NamedTempFile;

const STATE_FILE_PATH: &str = "/var/lib/trading-engine/execution_state.json";
const MAX_NONCE_CACHE_SIZE: usize = 1_000_000;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ExecutionState {
    pub current_epoch: u64,
    pub last_accepted_sequence: u64,
    pub used_nonces: HashSet<String>,
    pub last_broker_sequence: u64,
}

impl ExecutionState {
    pub fn new() -> Self {
        ExecutionState {
            current_epoch: 1, // Controlled by startup attestation
            last_accepted_sequence: 0,
            used_nonces: HashSet::new(),
            last_broker_sequence: 0,
        }
    }
}

pub struct StateStore {
    state: ExecutionState,
}

impl StateStore {
    pub fn load_or_init() -> Result<Self, String> {
        let path = Path::new(STATE_FILE_PATH);
        
        if !path.exists() {
            let mut store = StateStore { state: ExecutionState::new() };
            store.atomic_commit().map_err(|e| format!("Failed to init state: {}", e))?;
            return Ok(store);
        }

        let mut file = File::open(path).map_err(|e| e.to_string())?;
        let mut contents = String::new();
        file.read_to_string(&mut contents).map_err(|e| e.to_string())?;

        let state: ExecutionState = serde_json::from_str(&contents)
            .map_err(|e| format!("State file corruption detected: {}", e))?;

        Ok(StateStore { state })
    }

    pub fn get_state(&self) -> &ExecutionState {
        &self.state
    }

    pub fn update_state<F>(&mut self, mutate_fn: F) -> Result<(), String> 
    where
        F: FnOnce(&mut ExecutionState),
    {
        mutate_fn(&mut self.state);
        
        // Prevent memory exhaustion attacks from nonce buildup
        if self.state.used_nonces.len() > MAX_NONCE_CACHE_SIZE {
            self.state.used_nonces.clear();
        }

        self.atomic_commit().map_err(|e| format!("Atomic commit failed: {}", e))
    }

    fn atomic_commit(&self) -> Result<(), std::io::Error> {
        let path = Path::new(STATE_FILE_PATH);
        let dir = path.parent().unwrap_or_else(|| Path::new("."));
        std::fs::create_dir_all(dir)?;

        let mut temp_file = NamedTempFile::new_in(dir)?;
        let data = serde_json::to_vec(&self.state)?;

        temp_file.write_all(&data)?;
        temp_file.flush()?;
        temp_file.as_file_mut().sync_all()?; // Hardware flush guarantee
        
        temp_file.persist(STATE_FILE_PATH)?;
        Ok(())
    }
}