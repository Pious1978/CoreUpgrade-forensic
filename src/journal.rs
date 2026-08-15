use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha384};
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use byteorder::{BigEndian, ReadBytesExt, WriteBytesExt};
use crate::durable_file::DurableFile;
use crate::execution_events::ExecutionEvent;

const MAGIC_HEADER: [u8; 4] = [0x54, 0x52, 0x44, 0x45]; // TRDE
const COMMIT_MARKER: [u8; 4] = [0x43, 0x4F, 0x4D, 0x4D]; // COMM
const PROTOCOL_VERSION: &str = "TRADING_ENGINE_EXECUTION_JOURNAL_V3";
const GENESIS_HASH: &str = "GENESIS_HASH_000000000000000000000000000000000000000000000000";
const SHA384_BYTES: usize = 48;
const MAX_TRANSACTION_PAYLOAD_BYTES: usize = 16 * 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionPayload {
    pub version: String,
    pub transaction_id: u64,
    pub previous_hash: String,
    pub timestamp_ns: i128,
    pub events: Vec<ExecutionEvent>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionRecord {
    pub protocol_version: String,
    pub transaction_id: u64,
    pub previous_hash: String,
    pub timestamp_ns: i128,
    pub events: Vec<ExecutionEvent>,
    pub checksum: String,
}

pub struct DurableJournal {
    file: Box<dyn DurableFile>,
    file_path: String,
    last_transaction_id: u64,
    last_hash: String,
}

impl DurableJournal {
    pub fn new(file_path: &str) -> Self {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .open(file_path)
            .unwrap_or_else(|e| panic!("Failed to open durable journal '{}': {}", file_path, e));

        let mut journal = Self {
            file: Box::new(file),
            file_path: file_path.to_string(),
            last_transaction_id: 0,
            last_hash: GENESIS_HASH.to_string(),
        };

        journal.file.seek(SeekFrom::End(0)).unwrap_or_else(|e| panic!("Failed to position journal at EOF: {}", e));
        journal
    }

    pub fn with_file(file: Box<dyn DurableFile>) -> Self {
        Self {
            file,
            file_path: "memory_fault_injecting_journal".to_string(),
            last_transaction_id: 0,
            last_hash: GENESIS_HASH.to_string(),
        }
    }

    pub fn last_transaction_id(&self) -> u64 {
        self.last_transaction_id
    }

    pub fn into_inner_file(self) -> Box<dyn DurableFile> {
        self.file
    }

    pub fn recover_and_verify(&mut self) -> Result<Vec<ExecutionEvent>, String> {
        let records = self.recover_verified_records_internal()?;
        let mut events = Vec::new();
        for record in records {
            events.extend(record.events);
        }
        Ok(events)
    }

    pub fn recover_verified_records(&mut self) -> Result<Vec<TransactionRecord>, String> {
        self.recover_verified_records_internal()
    }

    fn recover_verified_records_internal(&mut self) -> Result<Vec<TransactionRecord>, String> {
        self.file.seek(SeekFrom::Start(0)).map_err(|e| format!("Journal seek failed: {}", e))?;

        let mut records = Vec::new();
        let mut expected_tx_id = 1u64;
        let mut expected_previous_hash = GENESIS_HASH.to_string();
        let mut last_valid_offset = 0u64;

        loop {
            let frame_start = self.file.stream_position().map_err(|e| format!("Journal position failed: {}", e))?;

            let mut magic = [0u8; 4];
            match self.file.read_exact(&mut magic) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => { break; }
                Err(e) => { return Err(format!("FATAL JOURNAL I/O ERROR at offset {}: {}", frame_start, e)); }
            }

            if magic != MAGIC_HEADER {
                return Err(format!("FATAL CORRUPTION: Invalid magic header at offset {}", frame_start));
            }

            let payload_len = match self.file.read_u32::<BigEndian>() {
                Ok(len) => len as usize,
                Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                    self.truncate_durable_tail(last_valid_offset, "truncated frame length")?;
                    break;
                }
                Err(e) => { return Err(format!("FATAL JOURNAL I/O ERROR while reading length: {}", e)); }
            };

            if payload_len == 0 || payload_len > MAX_TRANSACTION_PAYLOAD_BYTES {
                return Err(format!("FATAL CORRUPTION: Invalid payload length {} at offset {}", payload_len, frame_start));
            }

            let mut payload_bytes = vec![0u8; payload_len];
            match self.file.read_exact(&mut payload_bytes) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                    self.truncate_durable_tail(last_valid_offset, "truncated transaction payload")?;
                    break;
                }
                Err(e) => { return Err(format!("FATAL JOURNAL I/O ERROR while reading payload: {}", e)); }
            }

            let mut stored_checksum = [0u8; SHA384_BYTES];
            match self.file.read_exact(&mut stored_checksum) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                    self.truncate_durable_tail(last_valid_offset, "truncated transaction checksum")?;
                    break;
                }
                Err(e) => { return Err(format!("FATAL JOURNAL I/O ERROR while reading checksum: {}", e)); }
            }

            let mut marker = [0u8; 4];
            match self.file.read_exact(&mut marker) {
                Ok(()) => {}
                Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                    self.truncate_durable_tail(last_valid_offset, "truncated commit marker")?;
                    break;
                }
                Err(e) => { return Err(format!("FATAL JOURNAL I/O ERROR while reading commit marker: {}", e)); }
            }

            if marker != COMMIT_MARKER {
                return Err(format!("FATAL CORRUPTION: Invalid commit marker at offset {}", frame_start));
            }

            let computed_checksum = Self::calculate_frame_checksum(&payload_bytes);
            if computed_checksum != stored_checksum {
                return Err(format!("FATAL CORRUPTION: SHA-384 checksum mismatch at offset {}", frame_start));
            }

            let tx: TransactionPayload = serde_json::from_slice(&payload_bytes)
                .map_err(|e| format!("FATAL CORRUPTION: Invalid transaction payload at offset {}: {}", frame_start, e))?;

            if tx.version != PROTOCOL_VERSION {
                return Err(format!("FATAL PROTOCOL ERROR: Unsupported journal version '{}' at TX {}", tx.version, tx.transaction_id));
            }

            if tx.transaction_id != expected_tx_id {
                return Err(format!("FATAL CORRUPTION: Expected transaction ID {}, got {}", expected_tx_id, tx.transaction_id));
            }

            if tx.previous_hash != expected_previous_hash {
                return Err(format!("FATAL CORRUPTION: Hash-chain continuity failure at TX {}", tx.transaction_id));
            }

            let checksum_hex = hex::encode(stored_checksum);
            records.push(TransactionRecord {
                protocol_version: tx.version,
                transaction_id: tx.transaction_id,
                previous_hash: tx.previous_hash,
                timestamp_ns: tx.timestamp_ns,
                events: tx.events,
                checksum: checksum_hex.clone(),
            });

            expected_previous_hash = checksum_hex;
            expected_tx_id = expected_tx_id.checked_add(1).ok_or_else(|| "FATAL: Transaction ID exhausted u64 namespace".to_string())?;
            last_valid_offset = self.file.stream_position().map_err(|e| format!("Journal position failed: {}", e))?;
        }

        self.last_transaction_id = expected_tx_id - 1;
        self.last_hash = expected_previous_hash;
        self.file.seek(SeekFrom::End(0)).map_err(|e| format!("Failed to seek journal EOF: {}", e))?;

        Ok(records)
    }

    pub fn commit_transaction(&mut self, events: Vec<ExecutionEvent>, timestamp_ns: i128) -> Result<u64, String> {
        let tx_id = self.last_transaction_id.checked_add(1).ok_or_else(|| "FATAL: Transaction ID exhausted u64 namespace".to_string())?;

        self.file.seek(SeekFrom::End(0)).map_err(|e| format!("Journal seek-to-end failed: {}", e))?;

        let payload = TransactionPayload {
            version: PROTOCOL_VERSION.to_string(),
            transaction_id: tx_id,
            previous_hash: self.last_hash.clone(),
            timestamp_ns,
            events,
        };

        let payload_bytes = serde_json::to_vec(&payload).map_err(|e| e.to_string())?;
        if payload_bytes.len() > MAX_TRANSACTION_PAYLOAD_BYTES {
            return Err(format!("Transaction payload {} exceeds maximum {} bytes", payload_bytes.len(), MAX_TRANSACTION_PAYLOAD_BYTES));
        }

        let checksum_bytes = Self::calculate_frame_checksum(&payload_bytes);

        self.file.write_all(&MAGIC_HEADER).map_err(|e| e.to_string())?;
        self.file.write_u32::<BigEndian>(payload_bytes.len() as u32).map_err(|e| e.to_string())?;
        self.file.write_all(&payload_bytes).map_err(|e| e.to_string())?;
        self.file.write_all(&checksum_bytes).map_err(|e| e.to_string())?;
        self.file.flush().map_err(|e| e.to_string())?;
        self.file.sync_data().map_err(|e| format!("Phase-1 sync failed: {}", e))?;

        self.file.write_all(&COMMIT_MARKER).map_err(|e| e.to_string())?;
        self.file.flush().map_err(|e| e.to_string())?;
        self.file.sync_data().map_err(|e| format!("Phase-2 sync failed: {}", e))?;

        self.last_transaction_id = tx_id;
        self.last_hash = hex::encode(checksum_bytes);

        Ok(tx_id)
    }

    fn calculate_frame_checksum(payload_bytes: &[u8]) -> [u8; SHA384_BYTES] {
        let mut hasher = Sha384::new();
        hasher.update(MAGIC_HEADER);
        hasher.update(PROTOCOL_VERSION.as_bytes());
        hasher.update(&(payload_bytes.len() as u32).to_be_bytes());
        hasher.update(payload_bytes);
        hasher.update(COMMIT_MARKER);
        hasher.finalize().into()
    }

    fn truncate_durable_tail(&mut self, valid_offset: u64, reason: &str) -> Result<(), String> {
        eprintln!("WARNING: Torn journal tail detected ({}). Truncating journal to verified offset {}.", reason, valid_offset);
        self.file.set_len(valid_offset).map_err(|e| format!("Journal truncation failed: {}", e))?;
        self.file.sync_data().map_err(|e| format!("Journal truncation durability sync failed: {}", e))?;
        self.file.seek(SeekFrom::Start(valid_offset)).map_err(|e| format!("Journal seek after truncation failed: {}", e))?;
        Ok(())
    }
}