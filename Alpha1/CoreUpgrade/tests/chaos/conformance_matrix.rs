use proptest::prelude::*;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::fs::File;
use std::io::Write;

use crate::generators::{arbitrary_execution_scenario, ExecutionScenario};
use crate::fault_injector::{FaultInjectingFile, InjectedCrash, JournalFaultPoint, FaultAction};
use crate::chaos_scenario_runner::ScenarioRunner;
use crate::oracle::assert_five_laws_of_execution;

fn dump_chaos_artifact(seed: [u8; 32], violated_law: &str, trace: &[crate::chaos_scenario_runner::TraceEntry], journal_bytes: &[u8]) {
    let _ = std::fs::create_dir_all("./chaos_artifacts");
    let artifact_id = format!("CHAOS-{:x}", md5::compute(&seed));
    if let Ok(mut file) = File::create(format!("./chaos_artifacts/{}.log", artifact_id)) {
        let _ = writeln!(file, "========================================");
        let _ = writeln!(file, "FAILURE ARTIFACT: {}", artifact_id);
        let _ = writeln!(file, "VIOLATED LAW: {}", violated_law);
        let _ = writeln!(file, "SEED: {:?}", seed);
        let _ = writeln!(file, "========================================");
        let _ = writeln!(file, "MINIMAL TRACE:");
        for entry in trace {
            let _ = writeln!(file, "Step {}: {:?}", entry.step, entry.action);
        }
        let _ = writeln!(file, "========================================");
        let _ = writeln!(file, "JOURNAL HEX DUMP ({} bytes):", journal_bytes.len());
        let _ = writeln!(file, "{}", hex::encode(journal_bytes));
    }
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(100_000))]

    // -------------------------------------------------------------------------
    // MATRIX 1: PHYSICAL JOURNAL BOUNDARY FUZZING
    // -------------------------------------------------------------------------
    #[test]
    fn matrix_01_journal_boundary_fuzzing(
        scenario in arbitrary_execution_scenario(),
        seed_bytes in prop::array::uniform32(any::<u8>())
    ) {
        let journal_path = format!("/tmp/journal_matrix_1_{}.log", hex::encode(&seed_bytes[..4]));
        let mut runner = ScenarioRunner::new(journal_path.clone());
        
        let result = catch_unwind(AssertUnwindSafe(|| {
            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                runner.run_phase_a_execute(scenario.actions).await.unwrap();
                runner.run_phase_b_recover().await.unwrap();
            });
        }));

        if result.is_err() {
            dump_chaos_artifact(seed_bytes, "LAW 1 (Durability/TornTail)", &runner.trace, &runner.get_raw_journal_bytes());
            panic!("Matrix 1: Journal Boundary Fuzzing Failed");
        }
        let _ = std::fs::remove_file(journal_path);
    }

    // -------------------------------------------------------------------------
    // MATRIX 2: CRASH-POINT FUZZING (The I/O Boundary)
    // -------------------------------------------------------------------------
    #[test]
    fn matrix_02_crash_point_fuzzing(
        scenario in arbitrary_execution_scenario(),
        crash_tx_index in 0usize..20,
        seed_bytes in prop::array::uniform32(any::<u8>()),
        fault_point in prop_oneof![
            Just(JournalFaultPoint::BeforeMagic),
            Just(JournalFaultPoint::AfterLength),
            Just(JournalFaultPoint::DuringChecksum),
            Just(JournalFaultPoint::BeforeFirstSync),
            Just(JournalFaultPoint::AfterFirstSync),
            Just(JournalFaultPoint::DuringCommitMarker),
            Just(JournalFaultPoint::BeforeSecondSync),
        ]
    ) {
        let journal_path = format!("/tmp/journal_matrix_2_{}.log", hex::encode(&seed_bytes[..4]));
        let crash_cfg = InjectedCrash {
            transaction_index: crash_tx_index,
            fault_point,
            action: FaultAction::Crash,
        };

        let mut runner = ScenarioRunner::new_with_fault(journal_path.clone(), crash_cfg);
        let result = catch_unwind(AssertUnwindSafe(|| {
            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                let _ = runner.run_phase_a_execute(scenario.actions).await;
                runner.run_phase_b_recover().await.unwrap();
                runner.run_phase_c_converge().await.unwrap();
                
                assert_five_laws_of_execution(
                    &runner.reference, 
                    &runner.broker, 
                    runner.gateway.as_ref().unwrap(), 
                    &journal_path
                );
            });
        }));

        if result.is_err() {
            dump_chaos_artifact(seed_bytes, "LAW 1-5 (Crash-Point Integrity)", &runner.trace, &runner.get_raw_journal_bytes());
            panic!("Matrix 2: Crash-Point Fuzzing Failed");
        }
        let _ = std::fs::remove_file(journal_path);
    }

    // -------------------------------------------------------------------------
    // MATRIX 3: ADVERSARIAL BROKER PERMUTATIONS
    // -------------------------------------------------------------------------
    #[test]
    fn matrix_03_adversarial_broker_permutations(
        scenario in arbitrary_execution_scenario(),
        seed_bytes in prop::array::uniform32(any::<u8>())
    ) {
        let journal_path = format!("/tmp/journal_matrix_3_{}.log", hex::encode(&seed_bytes[..4]));
        let mut runner = ScenarioRunner::new(journal_path.clone());
        
        let result = catch_unwind(AssertUnwindSafe(|| {
            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                runner.run_phase_a_execute(scenario.actions).await.unwrap();
                runner.run_phase_c_converge().await.unwrap();
                
                assert_five_laws_of_execution(
                    &runner.reference, 
                    &runner.broker, 
                    runner.gateway.as_ref().unwrap(), 
                    &journal_path
                );
            });
        }));

        if result.is_err() {
            dump_chaos_artifact(seed_bytes, "LAW 3/4 (Adversarial Broker Convergence)", &runner.trace, &runner.get_raw_journal_bytes());
            panic!("Matrix 3: Adversarial Broker Permutations Failed");
        }
        let _ = std::fs::remove_file(journal_path);
    }

    // -------------------------------------------------------------------------
    // MATRIX 4: FULL COMBINED CHAOS
    // -------------------------------------------------------------------------
    #[test]
    fn matrix_04_full_combined_chaos(
        scenario in arbitrary_execution_scenario(),
        crash_tx_index in 0usize..10,
        seed_bytes in prop::array::uniform32(any::<u8>())
    ) {
        let journal_path = format!("/tmp/journal_matrix_4_{}.log", hex::encode(&seed_bytes[..4]));
        let crash_cfg = InjectedCrash {
            transaction_index: crash_tx_index,
            fault_point: JournalFaultPoint::DuringCommitMarker,
            action: FaultAction::Crash,
        };

        let mut runner = ScenarioRunner::new_with_fault(journal_path.clone(), crash_cfg);
        let result = catch_unwind(AssertUnwindSafe(|| {
            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                let _ = runner.run_phase_a_execute(scenario.actions).await;
                runner.run_phase_b_recover().await.unwrap();
                runner.run_phase_c_converge().await.unwrap();
                
                assert_five_laws_of_execution(
                    &runner.reference, 
                    &runner.broker, 
                    runner.gateway.as_ref().unwrap(), 
                    &journal_path
                );
            });
        }));

        if result.is_err() {
            dump_chaos_artifact(seed_bytes, "ALL LAWS (Combined Chaos)", &runner.trace, &runner.get_raw_journal_bytes());
            panic!("Matrix 4: Full Combined Chaos Failed");
        }
        let _ = std::fs::remove_file(journal_path);
    }
}