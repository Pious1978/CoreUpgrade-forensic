use proptest::prelude::*;
use gateway::execution_orchestrator::ExecutionOrchestrator;
use gateway::journal::DurableJournal;

use crate::simulated_broker::SimulatedBroker;
use crate::generators::{ExecutionScenario, Action};

proptest! {
    #![proptest_config(ProptestConfig::with_cases(1000))]
    
    #[test]
    fn crash_recovery_never_creates_or_loses_economic_effect(
        scenario in arbitrary_execution_scenario()
    ) {
        // 1. Run the Reference Simulation (Crash-Free)
        let reference_broker = SimulatedBroker::new();
        let reference_state = run_scenario_without_faults(&scenario, &reference_broker);

        // 2. Run the Adversarial Simulation (With Faults & Crashes)
        let adversarial_broker = SimulatedBroker::new();
        let crashed_state = run_scenario_with_faults_and_recovery(&scenario, &adversarial_broker);

        // 3. ORACLE ASSERTIONS

        // Invariant 1: Journal replay perfectly reconstructs the projection
        assert_projection_equals_journal_replay(&crashed_state);

        // Invariant 2: External reality was never duplicated
        // The simulated broker's absolute truth must match the reference broker's truth
        assert_eq!(
            reference_broker.external_truth.lock().blocking_lock().len(),
            adversarial_broker.external_truth.lock().blocking_lock().len(),
            "FATAL: Crash recovery caused duplicate external submission"
        );

        // Invariant 3: Economic conservation
        // currently_reserved = original_exposure - cumulative_released
        assert_economic_effects_are_conservative(&crashed_state);
        
        // Invariant 4: No state transitions violated
        assert_strict_state_machine_compliance(&crashed_state.journal);
    }
}

// ---------------------------------------------------------
// Oracle Helpers
// ---------------------------------------------------------

fn assert_economic_effects_are_conservative(state: &ExecutionOrchestrator) {
    for (order_id, record) in state.get_active_orders() {
        if let (Some(original), Some(released)) = (&record.original_exposure, &record.cumulative_released_exposure) {
            
            // Risk released must never exceed risk reserved
            assert!(
                released.units <= original.units,
                "FATAL: Order {} released more risk ({}) than originally reserved ({})",
                order_id, released.units, original.units
            );

            // Fills must never exceed requested quantity
            assert!(
                record.cumulative_filled_quantity <= record.requested_quantity,
                "FATAL: Order {} filled {} which exceeds requested {}",
                order_id, record.cumulative_filled_quantity, record.requested_quantity
            );
        }
    }
}

fn assert_projection_equals_journal_replay(crashed_state: &ExecutionOrchestrator) {
    let mut verification_journal = DurableJournal::new(crashed_state.journal_path());
    let recovered_events = verification_journal.recover_and_verify().expect("Journal must be valid");
    
    let mut rebuilt_orchestrator = ExecutionOrchestrator::new(verification_journal);
    for event in recovered_events {
        rebuilt_orchestrator.apply_event_for_recovery(event).expect("Replayed events must be legally valid");
    }

    assert_eq!(
        crashed_state.get_total_pending_exposure().units,
        rebuilt_orchestrator.get_total_pending_exposure().units,
        "FATAL: Memory projection diverges from disk recovery"
    );
}