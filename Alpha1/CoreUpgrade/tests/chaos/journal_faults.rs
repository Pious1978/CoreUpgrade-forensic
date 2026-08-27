use gateway::journal::DurableJournal;
use gateway::execution_events::{ExecutionEvent, GatewayUncertainty};
use crate::fault_injector::{FaultInjectingFile, InjectedCrash, JournalFaultPoint, FaultAction};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RecoveryExpectation {
    MustRecover,
    MustTruncate,
    MustFailClosed,
}

fn create_test_event() -> Vec<ExecutionEvent> {
    vec![ExecutionEvent::Uncertainty(GatewayUncertainty::SubmissionUnknown {
        order_id: "ORD-TEST-1".into(),
        reason: "Chaos conformance test payload".into(),
    })]
}

/// Core test runner mapping injected faults to expected recovery behavior.
pub fn run_journal_fault_test(
    crash_cfg: InjectedCrash, 
    expected: RecoveryExpectation, 
    corrupt_action: Option<Box<dyn FnOnce(&mut Vec<u8>)>>
) {
    // 1. Initialize fault-injecting backing file
    let file = Box::new(FaultInjectingFile::new(crash_cfg.clone(), vec![]));
    let mut journal = DurableJournal::with_file(file);

    // Commit a valid baseline transaction (TX 1)
    journal.commit_transaction(create_test_event(), 1000).unwrap();

    // 2. Attempt writing a faulted transaction (TX 2) which triggers the fault injector
    let _ = journal.commit_transaction(create_test_event(), 1001);

    // Extract the raw bytes written so far
    let mut raw_bytes = journal.into_inner_file().inner.into_inner();

    // Apply optional out-of-band corruption (e.g., bit-flips simulating bit-rot)
    if let Some(action) = corrupt_action {
        action(&mut raw_bytes);
    }

    // 3. Attempt Recovery using a clean recovery file wrapper loaded with the surviving bytes
    let recovery_file = Box::new(FaultInjectingFile::new(InjectedCrash { action: FaultAction::None, ..crash_cfg }, raw_bytes));
    let mut recovery_journal = DurableJournal::with_file(recovery_file);
    let recovery_result = recovery_journal.recover_and_verify();

    // 4. Assert against the explicit cryptographic contract
    match expected {
        RecoveryExpectation::MustRecover | RecoveryExpectation::MustTruncate => {
            assert!(
                recovery_result.is_ok(), 
                "CONTRACT VIOLATION: Expected safe recovery/truncation, but recovery failed with: {:?}", 
                recovery_result.err()
            );
            // Verify that exactly the valid baseline transaction survived
            assert_eq!(
                recovery_journal.last_transaction_id(), 1,
                "CONTRACT VIOLATION: Expected state to roll back to valid prefix (TX 1), but last_transaction_id is {}", 
                recovery_journal.last_transaction_id()
            );
        }
        RecoveryExpectation::MustFailClosed => {
            assert!(
                recovery_result.is_err(), 
                "CONTRACT VIOLATION: Expected fail-closed corruption halt, but recovery unexpectedly succeeded."
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_torn_payload_truncates_safely() {
        let crash_cfg = InjectedCrash {
            transaction_index: 1, // Target the second transaction
            fault_point: JournalFaultPoint::DuringPayload,
            action: FaultAction::ShortWrite(10), // Writes only 10 bytes of payload, leaving a torn tail
        };

        run_journal_fault_test(crash_cfg, RecoveryExpectation::MustTruncate, None);
    }

    #[test]
    fn test_torn_commit_marker_truncates_safely() {
        let crash_cfg = InjectedCrash {
            transaction_index: 1,
            fault_point: JournalFaultPoint::DuringCommitMarker,
            action: FaultAction::ShortWrite(2), // Writes "CO", missing "MM" of the COMMIT_MARKER
        };

        run_journal_fault_test(crash_cfg, RecoveryExpectation::MustTruncate, None);
    }

    #[test]
    fn test_short_write_during_checksum_truncates_safely() {
        let crash_cfg = InjectedCrash {
            transaction_index: 1,
            fault_point: JournalFaultPoint::DuringChecksum,
            action: FaultAction::ShortWrite(12), // Truncates the 48-byte SHA-384 checksum
        };

        run_journal_fault_test(crash_cfg, RecoveryExpectation::MustTruncate, None);
    }

    #[test]
    fn test_corrupt_checksum_fails_closed() {
        let crash_cfg = InjectedCrash {
            transaction_index: 1,
            fault_point: JournalFaultPoint::AfterSecondSync,
            action: FaultAction::None, // Complete write, but we will inject bit-rot afterward
        };

        // Corrupt a byte in the payload area of the completed frame
        let corruption = Box::new(|bytes: &mut Vec<u8>| {
            if bytes.len() > 30 {
                bytes[30] ^= 0xFF; // Bit-flip mutation
            }
        });

        run_journal_fault_test(crash_cfg, RecoveryExpectation::MustFailClosed, Some(corruption));
    }

    #[test]
    fn test_corrupt_magic_header_fails_closed() {
        let crash_cfg = InjectedCrash {
            transaction_index: 1,
            fault_point: JournalFaultPoint::AfterSecondSync,
            action: FaultAction::None,
        };

        // Corrupt the magic header bytes ("TRDE")
        let corruption = Box::new(|bytes: &mut Vec<u8>| {
            if bytes.len() > 4 {
                bytes[0] = 0x00; 
            }
        });

        run_journal_fault_test(crash_cfg, RecoveryExpectation::MustFailClosed, Some(corruption));
    }
}