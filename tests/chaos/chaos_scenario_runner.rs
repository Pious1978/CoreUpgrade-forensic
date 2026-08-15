use crate::fault_injector::{FaultInjectingFile, InjectedCrash};

pub struct ScenarioRunner {
    pub reference: ReferenceModel,
    pub broker: Arc<SimulatedBroker>,
    pub gateway: Option<ExecutionOrchestrator>,
    pub journal_path: String,
    pub active_fault: Option<InjectedCrash>,
}

impl ScenarioRunner {
    pub fn new(journal_path: String, fault: Option<InjectedCrash>) -> Self {
        // Wire the fault injector directly into the journal I/O
        let file = Box::new(FaultInjectingFile::new(fault.clone(), vec![]));
        let journal = DurableJournal::with_file(file);
        
        Self {
            reference: ReferenceModel::new(),
            broker: Arc::new(SimulatedBroker::new()),
            gateway: Some(ExecutionOrchestrator::recover_and_start(journal).unwrap()),
            journal_path,
            active_fault: fault,
        }
    }

    pub async fn execute_step(&mut self, step: ScenarioStep) -> Result<(), String> {
        // 1. Process Gateway Intent
        if let Some(cmd) = step.command {
            self.reference.apply_command(&cmd).expect("Generator provided illegal command to Reference");
            let gw = self.gateway.as_mut().expect("Gateway is down");
            // Map command to Orchestrator API...
        }

        // 2. Process Chaos/Network Failure
        if let Some(ChaosAction::NetworkTimeout { order_id }) = step.chaos {
            let gw = self.gateway.as_mut().unwrap();
            // Gateway derives SubmissionUnknown or CancelUnknown
            gw.process_broker_fact(ExecutionEvent::SubmissionUnknown { order_id: order_id.to_string(), reason: "Timeout".into() }, 1000)?;
        }

        // 3. Process Authoritative Broker Fact
        if let Some(fact) = step.broker_fact {
            self.reference.apply_fact(&fact).expect("Generator provided illegal fact to Reference");
            self.broker.inject_adversarial_fact(&fact).await;
            
            // Note: We only feed this to the gateway if it's pushed, otherwise it's discovered in Reconcile
            if let Some(gw) = self.gateway.as_mut() {
                // Fact -> Derived RiskRelease -> Single Journal Transaction
                gw.process_broker_fact(fact.into_gateway_event(), 1000)?;
            }
        }
        Ok(())
    }

    pub async fn crash_and_recover(&mut self) -> Result<(), String> {
        // Total memory annihilation
        drop(self.gateway.take());

        // Extract the bytes that physically survived the injected fault
        let raw_bytes = std::fs::read(&self.journal_path).unwrap();
        
        // Re-mount with a clean, fault-free file wrapper for recovery phase
        let recovery_file = Box::new(FaultInjectingFile::new(None, raw_bytes));
        let mut journal = DurableJournal::with_file(recovery_file);
        
        // I1: Journal Integrity (Must succeed or cleanly truncate, never ambiguously fail)
        let gw = ExecutionOrchestrator::recover_and_start(journal).expect("Journal Recovery Contract Violated");
        self.gateway = Some(gw);
        
        Ok(())
    }
}