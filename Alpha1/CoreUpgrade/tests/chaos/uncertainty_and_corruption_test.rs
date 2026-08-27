use tokio::runtime::Runtime;
use gateway::execution_events::{ExecutionEvent, GatewayIntent, BrokerFact, BrokerFactEvent, GatewayCommand, GatewayUncertainty};
use gateway::execution_orchestrator::ExecutionOrchestrator;
use gateway::journal::DurableJournal;
use gateway::money::Money;

#[path = "reference_model.rs"]
mod reference_model;
#[path = "simulated_broker.rs"]
mod simulated_broker;

use reference_model::ReferenceModel;
use simulated_broker::SimulatedBroker;

#[test]
fn test_epistemic_boundary_submission_unknown_then_acknowledged() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        let journal_path = "epistemic_boundary.journal";
        let _ = std::fs::remove_file(journal_path);

        let mut reference = ReferenceModel::new();
        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();

        let order_id_u8: u8 = 10;
        let order_id_str = format!("ORD-{}", order_id_u8);
        let broker_order_id = SimulatedBroker::broker_order_id_for(order_id_u8);
        let exposure = Money::new(5_000_000, "USD", 4);

        // 1. Admit and Reserve
        let admit_cmd = GatewayCommand::Admit { order_id: order_id_u8, quantity: 50, exposure: 5_000_000 };
        reference.apply_command(&admit_cmd).unwrap();
        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: order_id_str.clone(),
            sequence_number: 1,
            request_nonce: "NONCE-EP-1".into(),
            certificate_generation: 1,
            instrument: "MSFT".into(),
            requested_quantity: 50,
        });
        gateway.process_event_transaction(vec![admit_event], 2000).unwrap();

        let reserve_event = ExecutionEvent::Intent(GatewayIntent::RiskReserved {
            order_id: order_id_str.clone(),
            notional_exposure: exposure.clone(),
        });
        gateway.process_event_transaction(vec![reserve_event], 2001).unwrap();

        // 2. Submit Order Starts
        let submit_cmd = GatewayCommand::Submit { order_id: order_id_u8 };
        reference.apply_command(&submit_cmd).unwrap();
        gateway.mark_submission_started(&order_id_str, "IDEMP-SUB-EP", 2002).unwrap();

        // 3. Enter SubmissionUnknown (Epistemic Boundary check before Acknowledged)
        let unk_event = ExecutionEvent::Uncertainty(GatewayUncertainty::SubmissionUnknown {
            order_id: order_id_str.clone(),
            reason: "Transport timeout/uncertainty".into(),
        });
        gateway.process_event_transaction(vec![unk_event], 2003).unwrap();

        let snap_before = gateway.projected_snapshot();
        let order_before = snap_before.get(&order_id_str).unwrap();
        assert_eq!(order_before.state, "Unknown");
        assert!(!order_before.has_broker_identity);

        // 4. Broker Acknowledges / Recovers from Uncertainty
        let ack_event = ExecutionEvent::Fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            requested_quantity: 50,
            original_exposure: exposure.clone(),
        });
        gateway.process_broker_fact(ack_event, 2004).unwrap();

        let snap_after = gateway.projected_snapshot();
        let order_after = snap_after.get(&order_id_str).unwrap();
        assert_eq!(order_after.state, "Acknowledged");
        assert!(order_after.has_broker_identity);
        assert_eq!(order_after.broker_order_id.as_ref().unwrap(), &broker_order_id);

        let _ = std::fs::remove_file(journal_path);
    });
}

#[test]
fn test_submission_unknown_then_accept() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        let journal_path = "sub_unknown_accept.journal";
        let _ = std::fs::remove_file(journal_path);

        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();

        let order_id_str = "ORD-20".to_string();
        let broker_order_id = "BROKER-ORD-20".to_string();
        let exposure = Money::new(2_000_000, "USD", 4);

        // Setup admitted state
        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: order_id_str.clone(),
            sequence_number: 1,
            request_nonce: "NONCE-20".into(),
            certificate_generation: 1,
            instrument: "GOOG".into(),
            requested_quantity: 10,
        });
        gateway.process_event_transaction(vec![admit_event], 3000).unwrap();
        gateway.mark_submission_started(&order_id_str, "IDEMP-20", 3001).unwrap();

        // Uncertainty & Recovery via Accept
        let unk = ExecutionEvent::Uncertainty(GatewayUncertainty::SubmissionUnknown {
            order_id: order_id_str.clone(),
            reason: "Socket drop".into(),
        });
        gateway.process_event_transaction(vec![unk], 3002).unwrap();

        let accept = ExecutionEvent::Fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            requested_quantity: 10,
            original_exposure: exposure,
        });
        gateway.process_broker_fact(accept, 3003).unwrap();

        let snap = gateway.projected_snapshot();
        assert_eq!(snap.get(&order_id_str).unwrap().state, "Acknowledged");

        let _ = std::fs::remove_file(journal_path);
    });
}

#[test]
fn test_submission_unknown_then_reject() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        let journal_path = "sub_unknown_reject.journal";
        let _ = std::fs::remove_file(journal_path);

        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();

        let order_id_str = "ORD-21".to_string();

        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: order_id_str.clone(),
            sequence_number: 1,
            request_nonce: "NONCE-21".into(),
            certificate_generation: 1,
            instrument: "AMZN".into(),
            requested_quantity: 20,
        });
        gateway.process_event_transaction(vec![admit_event], 4000).unwrap();
        gateway.mark_submission_started(&order_id_str, "IDEMP-21", 4001).unwrap();

        let unk = ExecutionEvent::Uncertainty(GatewayUncertainty::SubmissionUnknown {
            order_id: order_id_str.clone(),
            reason: "Network partition".into(),
        });
        gateway.process_event_transaction(vec![unk], 4002).unwrap();

        let reject = ExecutionEvent::Fact(BrokerFact::BrokerRejected {
            order_id: order_id_str.clone(),
            reason: "Margin shortfall detected late".into(),
        });
        gateway.process_broker_fact(reject, 4003).unwrap();

        let snap = gateway.projected_snapshot();
        assert_eq!(snap.get(&order_id_str).unwrap().state, "Rejected");

        let _ = std::fs::remove_file(journal_path);
    });
}

#[test]
fn test_duplicate_acceptance_is_idempotent() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        let journal_path = "dup_accept.journal";
        let _ = std::fs::remove_file(journal_path);

        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();

        let order_id_str = "ORD-30".to_string();
        let broker_id = "B-30".to_string();
        let exposure = Money::new(1_000_000, "USD", 4);

        gateway.process_event_transaction(vec![
            ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
                order_id: order_id_str.clone(),
                sequence_number: 1,
                request_nonce: "N-30".into(),
                certificate_generation: 1,
                instrument: "TSLA".into(),
                requested_quantity: 5,
            })
        ], 5000).unwrap();
        gateway.mark_submission_started(&order_id_str, "ID-30", 5001).unwrap();

        let fact = BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: broker_id.clone(),
            requested_quantity: 5,
            original_exposure: exposure.clone(),
        };

        gateway.process_broker_fact(fact.clone(), 5002).unwrap();
        // Duplicate acknowledgment should succeed idempotently
        gateway.process_broker_fact(fact, 5003).unwrap();

        let snap = gateway.projected_snapshot();
        assert_eq!(snap.get(&order_id_str).unwrap().state, "Acknowledged");

        let _ = std::fs::remove_file(journal_path);
    });
}

#[test]
fn test_contradictory_acceptance_is_fatal() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        let journal_path = "contra_accept.journal";
        let _ = std::fs::remove_file(journal_path);

        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();

        let order_id_str = "ORD-31".to_string();
        let exposure = Money::new(1_000_000, "USD", 4);

        gateway.process_event_transaction(vec![
            ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
                order_id: order_id_str.clone(),
                sequence_number: 1,
                request_nonce: "N-31".into(),
                certificate_generation: 1,
                instrument: "NFLX".into(),
                requested_quantity: 5,
            })
        ], 6000).unwrap();
        gateway.mark_submission_started(&order_id_str, "ID-31", 6001).unwrap();

        gateway.process_broker_fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: "B-ID-1".into(),
            requested_quantity: 5,
            original_exposure: exposure.clone(),
        }, 6002).unwrap();

        // Contradictory broker ID / facts should trip fatal protection
        let res = gateway.process_broker_fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: "B-ID-CONFLICTING".into(),
            requested_quantity: 5,
            original_exposure: exposure,
        }, 6003);

        assert!(res.is_err());

        let _ = std::fs::remove_file(journal_path);
    });
}