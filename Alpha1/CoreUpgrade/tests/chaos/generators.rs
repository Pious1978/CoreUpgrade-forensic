#[derive(Debug, Clone)]
pub enum GatewayCommand {
    Admit { order_id: u8, quantity: u64, exposure: u64 },
    Submit { order_id: u8 },
    Cancel { order_id: u8 },
}

#[derive(Debug, Clone)]
pub enum BrokerFactEvent {
    Accepted { order_id: u8, broker_order_id: u8 },
    Rejected { order_id: u8 },
    Fill { order_id: u8, fill_id: u16, quantity: u64, remaining: u64 },
    CancelConfirmed { order_id: u8, remaining: u64 },
}

#[derive(Debug, Clone)]
pub enum ChaosAction {
    CrashAt { transaction: usize, fault_point: JournalFaultPoint, action: FaultAction },
    NetworkTimeout { order_id: u8 }, // Results in SubmissionUnknown or CancelUnknown
    TriggerReconciliation { order_id: u8 },
}

#[derive(Debug, Clone)]
pub struct ScenarioStep {
    pub command: Option<GatewayCommand>,
    pub broker_fact: Option<BrokerFactEvent>,
    pub chaos: Option<ChaosAction>,
}