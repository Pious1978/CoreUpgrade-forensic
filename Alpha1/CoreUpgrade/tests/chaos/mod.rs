proptest! {
    #![proptest_config(ProptestConfig::with_cases(1_000))]
    
    #[test]
    fn crash_recovery_preserves_terminal_economic_truth(
        scenario_actions in arbitrary_execution_scenario()
    ) {
        let mut runner = ScenarioRunner::new("/tmp/test_journal.log".into());
        
        // Phase A: Chaos
        runner.run_phase_a_execute(scenario_actions).unwrap();
        
        // Phase B: Final Recover
        runner.run_phase_b_recover().unwrap();
        
        // Phase C: Reconcile all unknowns
        runner.run_phase_c_converge().unwrap();
        
        // The Invariants
        assert_terminal_economic_convergence(&runner.reference, &runner.broker, runner.gateway.as_ref().unwrap());
        assert_epistemic_integrity(runner.gateway.as_ref().unwrap(), &runner.broker);
    }
}