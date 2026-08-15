use tokio::runtime::Runtime;

use gateway::execution_events::{ExecutionEvent, GatewayIntent, BrokerFact, BrokerFactEvent, GatewayCommand, GatewayUncertainty};
use gateway::execution_orchestrator::{ExecutionOrchestrator, EconomicView};
use gateway::journal::DurableJournal;
use gateway::money::Money;

#[path = "chaos/reference_model.rs"]
mod reference_model;
#[path = "chaos/simulated_broker.rs"]
mod simulated_broker;
#[path = "chaos/oracle.rs"]
mod oracle;

use reference_model::ReferenceModel;
use simulated_broker::SimulatedBroker;
use oracle::assert_five_laws_of_execution;

#[test]
fn test_deterministic_happy_path_and_oracle() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        let journal_path = "deterministic_happy_path.journal";
        let _ = std::fs::remove_file(journal_path);

        let mut reference = ReferenceModel::new();
        let mut broker = SimulatedBroker::new();
        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal)
            .expect("Gateway recovery failed");

        let order_id_u8: u8 = 1;
        let order_id_str = format!("ORD-{}", order_id_u8);
        let broker_order_id = SimulatedBroker::broker_order_id_for(order_id_u8);
        let exposure = Money::new(10_000_000, "USD", 4);

        // 1. Admit Order
        let admit_cmd = GatewayCommand::Admit { order_id: order_id_u8, quantity: 100, exposure: 10_000_000 };
        reference.apply_command(&admit_cmd).unwrap();

        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: order_id_str.clone(),
            sequence_number: 1,
            request_nonce: "NONCE-100".into(),
            certificate_generation: 1,
            instrument: "AAPL".into(),
            requested_quantity: 100,
        });
        gateway.process_event_transaction(vec![admit_event], 1000).unwrap();

        // 2. Reserve Risk
        let reserve_event = ExecutionEvent::Intent(GatewayIntent::RiskReserved {
            order_id: order_id_str.clone(),
            notional_exposure: exposure.clone(),
        });
        gateway.process_event_transaction(vec![reserve_event], 1001).unwrap();

        // 3. Submit Order
        let submit_cmd = GatewayCommand::Submit { order_id: order_id_u8 };
        reference.apply_command(&submit_cmd).unwrap();
        gateway.mark_submission_started(&order_id_str, "IDEMP-SUB-1", 1002).unwrap();

        // 4. Broker Acceptance
        let accept_fact_event = BrokerFactEvent::Accepted {
            order_id: order_id_u8,
            broker_order_id: broker_order_id.clone(),
            requested_quantity: 100,
            original_exposure: exposure.clone(),
        };
        reference.apply_fact(&accept_fact_event).unwrap();
        broker.inject_adversarial_fact(&accept_fact_event).await;

        let gw_accept_event = ExecutionEvent::Fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            requested_quantity: 100,
            original_exposure: exposure.clone(),
        });
        gateway.process_broker_fact(gw_accept_event, 1003).unwrap();

        // 5. Fill 40 units (F1)
        let fill_1_event = BrokerFactEvent::Fill {
            order_id: order_id_u8,
            fill_id: "FILL-001".into(),
            quantity: 40,
            remaining: 60,
            price: Money::new(100_000, "USD", 4),
        };
        reference.apply_fact(&fill_1_event).unwrap();
        broker.inject_adversarial_fact(&fill_1_event).await;

        let gw_fill_1 = ExecutionEvent::Fact(BrokerFact::FillReceived {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            broker_fill_id: "FILL-001".into(),
            fill_quantity: 40,
            price: Money::new(100_000, "USD", 4),
            remaining_quantity: 60,
        });
        gateway.process_broker_fact(gw_fill_1, 1004).unwrap();

        // 6. Fill remaining 60 units (F2) -> Terminal Filled
        let fill_2_event = BrokerFactEvent::Fill {
            order_id: order_id_u8,
            fill_id: "FILL-002".into(),
            quantity: 60,
            remaining: 0,
            price: Money::new(100_000, "USD", 4),
        };
        reference.apply_fact(&fill_2_event).unwrap();
        broker.inject_adversarial_fact(&fill_2_event).await;

        let gw_fill_2 = ExecutionEvent::Fact(BrokerFact::FillReceived {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            broker_fill_id: "FILL-002".into(),
            fill_quantity: 60,
            price: Money::new(100_000, "USD", 4),
            remaining_quantity: 0,
        });
        gateway.process_broker_fact(gw_fill_2, 1005).unwrap();

        // 7. Final Oracle Conformance Check
        assert_five_laws_of_execution(
            &reference,
            &broker,
            &gateway,
            journal_path,
            None,
            None,
            None,
            None,
        );

        let gw_snap = gateway.projected_snapshot();
        let final_order = gw_snap.get(&order_id_str).unwrap();
        assert_eq!(final_order.state, "Filled");
        assert_eq!(final_order.filled_qty, 100);
        assert_eq!(final_order.remaining_qty, 0);
        assert_eq!(final_order.reserved_exposure_units, 0);
        assert_eq!(final_order.released_exposure_units, exposure.units);
        assert!(final_order.has_broker_identity);
        assert_eq!(final_order.observed_fills.len(), 2);

        let _ = std::fs::remove_file(journal_path);
    });
}

#[test]
fn test_epistemic_boundary_submission_unknown_then_acknowledged() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        let journal_path = "epistemic_boundary.journal";
        let _ = std::fs::remove_file(journal_path);

        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();

        let order_id_u8: u8 = 10;
        let order_id_str = format!("ORD-{}", order_id_u8);
        let broker_order_id = SimulatedBroker::broker_order_id_for(order_id_u8);
        let exposure = Money::new(5_000_000, "USD", 4);

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

        gateway.mark_submission_started(&order_id_str, "IDEMP-SUB-EP", 2002).unwrap();

        let unk_event = ExecutionEvent::Uncertainty(GatewayUncertainty::SubmissionUnknown {
            order_id: order_id_str.clone(),
            reason: "Transport timeout/uncertainty".into(),
        });
        gateway.process_event_transaction(vec![unk_event], 2003).unwrap();

        let snap_before = gateway.projected_snapshot();
        let order_before = snap_before.get(&order_id_str).unwrap();
        assert_eq!(order_before.state, "Unknown");
        assert!(!order_before.has_broker_identity);

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

        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: order_id_str.clone(),
            sequence_number: 1,
            request_nonce: "NONCE-20".into(),
            certificate_generation: 1,
            instrument: "GOOG".into(),
            requested_quantity: 10,
        });
        gateway.process_event_transaction(vec![admit_event], 3000).unwrap();

        let reserve_event = ExecutionEvent::Intent(GatewayIntent::RiskReserved {
            order_id: order_id_str.clone(),
            notional_exposure: exposure.clone(),
        });
        gateway.process_event_transaction(vec![reserve_event], 3001).unwrap();

        gateway.mark_submission_started(&order_id_str, "IDEMP-20", 3002).unwrap();

        let unk = ExecutionEvent::Uncertainty(GatewayUncertainty::SubmissionUnknown {
            order_id: order_id_str.clone(),
            reason: "Socket drop".into(),
        });
        gateway.process_event_transaction(vec![unk], 3003).unwrap();

        let accept = ExecutionEvent::Fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            requested_quantity: 10,
            original_exposure: exposure,
        });
        gateway.process_broker_fact(accept, 3004).unwrap();

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
        let exposure = Money::new(2_000_000, "USD", 4);

        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: order_id_str.clone(),
            sequence_number: 1,
            request_nonce: "NONCE-21".into(),
            certificate_generation: 1,
            instrument: "AMZN".into(),
            requested_quantity: 20,
        });
        gateway.process_event_transaction(vec![admit_event], 4000).unwrap();

        let reserve_event = ExecutionEvent::Intent(GatewayIntent::RiskReserved {
            order_id: order_id_str.clone(),
            notional_exposure: exposure,
        });
        gateway.process_event_transaction(vec![reserve_event], 4001).unwrap();

        gateway.mark_submission_started(&order_id_str, "IDEMP-21", 4002).unwrap();

        let unk = ExecutionEvent::Uncertainty(GatewayUncertainty::SubmissionUnknown {
            order_id: order_id_str.clone(),
            reason: "Network partition".into(),
        });
        gateway.process_event_transaction(vec![unk], 4003).unwrap();

        let reject = ExecutionEvent::Fact(BrokerFact::BrokerRejected {
            order_id: order_id_str.clone(),
            reason: "Margin shortfall detected late".into(),
        });
        gateway.process_broker_fact(reject, 4004).unwrap();

        let snap = gateway.projected_snapshot();
        assert_eq!(snap.get(&order_id_str).unwrap().state, "BrokerRejected");

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

        gateway.process_event_transaction(vec![
            ExecutionEvent::Intent(GatewayIntent::RiskReserved {
                order_id: order_id_str.clone(),
                notional_exposure: exposure.clone(),
            })
        ], 5001).unwrap();

        gateway.mark_submission_started(&order_id_str, "ID-30", 5002).unwrap();

        let fact = ExecutionEvent::Fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: broker_id.clone(),
            requested_quantity: 5,
            original_exposure: exposure.clone(),
        });

        gateway.process_broker_fact(fact.clone(), 5003).unwrap();
        gateway.process_broker_fact(fact, 5004).unwrap();

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

        gateway.process_event_transaction(vec![
            ExecutionEvent::Intent(GatewayIntent::RiskReserved {
                order_id: order_id_str.clone(),
                notional_exposure: exposure.clone(),
            })
        ], 6001).unwrap();

        gateway.mark_submission_started(&order_id_str, "ID-31", 6002).unwrap();

        gateway.process_broker_fact(ExecutionEvent::Fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: "B-ID-1".into(),
            requested_quantity: 5,
            original_exposure: exposure.clone(),
        }), 6003).unwrap();

        let res = gateway.process_broker_fact(ExecutionEvent::Fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: "B-ID-CONFLICTING".into(),
            requested_quantity: 5,
            original_exposure: exposure,
        }), 6004);

        assert!(res.is_err());

        let _ = std::fs::remove_file(journal_path);
    });
}

#[test]
fn test_journal_corruption_magic_header_is_fatal() {
    let journal_path = "corrupt_magic.journal";
    let _ = std::fs::remove_file(journal_path);

    {
        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();
        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: "ORD-CORRUPT-1".into(),
            sequence_number: 1,
            request_nonce: "NONCE-C1".into(),
            certificate_generation: 1,
            instrument: "BTC".into(),
            requested_quantity: 1,
        });
        gateway.process_event_transaction(vec![admit_event], 1000).unwrap();
    }

    let mut data = std::fs::read(journal_path).unwrap();
    if !data.is_empty() {
        data[0] ^= 0xFF;
        std::fs::write(journal_path, &data).unwrap();
    }

    let journal = DurableJournal::new(journal_path);
    let recovery_result = ExecutionOrchestrator::recover_and_start(journal);
    assert!(recovery_result.is_err(), "Journal recovery with corrupted magic header must fail fatally");

    let _ = std::fs::remove_file(journal_path);
}

#[test]
fn test_journal_torn_tail_recovers_via_truncation() {
    let journal_path = "torn_tail_recover.journal";
    let _ = std::fs::remove_file(journal_path);

    {
        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();
        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: "ORD-CORRUPT-2".into(),
            sequence_number: 1,
            request_nonce: "NONCE-C2".into(),
            certificate_generation: 1,
            instrument: "ETH".into(),
            requested_quantity: 2,
        });
        gateway.process_event_transaction(vec![admit_event], 1000).unwrap();
    }

    let data = std::fs::read(journal_path).unwrap();
    if data.len() > 5 {
        let truncated_len = data.len() / 2;
        std::fs::write(journal_path, &data[..truncated_len]).unwrap();
    }

    let journal = DurableJournal::new(journal_path);
    let recovery_result = ExecutionOrchestrator::recover_and_start(journal);
    assert!(recovery_result.is_ok(), "Journal must gracefully recover from a crash-induced torn tail via automatic truncation");

    let _ = std::fs::remove_file(journal_path);
}

#[test]
fn test_journal_precise_torn_tail_truncation_preserves_prior_records() {
    let rt = Runtime::new().unwrap();
    rt.block_on(async {
        let journal_path = "precise_torn_tail.journal";
        let _ = std::fs::remove_file(journal_path);

        let order_id_str = "ORD-PRECISION-1".to_string();
        let offset_after_record_1;

        // 1. Write Record 1 (Order Admitted) and capture its byte boundary offset
        {
            let journal = DurableJournal::new(journal_path);
            let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();
            
            let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
                order_id: order_id_str.clone(),
                sequence_number: 1,
                request_nonce: "NONCE-P1".into(),
                certificate_generation: 1,
                instrument: "NVDA".into(),
                requested_quantity: 50,
            });
            gateway.process_event_transaction(vec![admit_event], 1000).unwrap();
            
            offset_after_record_1 = std::fs::metadata(journal_path).unwrap().len();
        }

        // 2. Write Record 2 (Risk Reserved) to establish a tail
        {
            let journal = DurableJournal::new(journal_path);
            let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();
            
            let reserve_event = ExecutionEvent::Intent(GatewayIntent::RiskReserved {
                order_id: order_id_str.clone(),
                notional_exposure: Money::new(5_000_000, "USD", 4),
            });
            gateway.process_event_transaction(vec![reserve_event], 1001).unwrap();
        }

        let total_len = std::fs::metadata(journal_path).unwrap().len();
        assert!(total_len > offset_after_record_1, "Record 2 should extend the file length");

        // 3. Test precise truncation points across Record 2's uncommitted footprint
        let test_cutpoints = [
            offset_after_record_1 + 1,
            offset_after_record_1 + (total_len - offset_after_record_1) / 2,
            total_len - 2,
        ];

        for &cutpoint in &test_cutpoints {
            let full_data = std::fs::read(journal_path).unwrap();
            if (cutpoint as usize) < full_data.len() {
                std::fs::write(journal_path, &full_data[..cutpoint as usize]).unwrap();

                let journal = DurableJournal::new(journal_path);
                let gateway = ExecutionOrchestrator::recover_and_start(journal)
                    .expect("Recovery failed on precision-truncated journal tail");

                let snap = gateway.projected_snapshot();
                let order = snap.get(&order_id_str).expect("Record 1 state must survive torn tail truncation");
                assert_eq!(order.requested_qty, 50, "Recovered state must match Record 1 invariant");
            }
        }

        let _ = std::fs::remove_file(journal_path);
    });
}

#[test]
fn test_journal_corruption_checksum_mismatch_is_fatal() {
    let journal_path = "corrupt_checksum.journal";
    let _ = std::fs::remove_file(journal_path);

    {
        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();
        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: "ORD-CORRUPT-3".into(),
            sequence_number: 1,
            request_nonce: "NONCE-C3".into(),
            certificate_generation: 1,
            instrument: "SOL".into(),
            requested_quantity: 10,
        });
        gateway.process_event_transaction(vec![admit_event], 1000).unwrap();
    }

    let mut data = std::fs::read(journal_path).unwrap();
    let len = data.len();
    if len > 10 {
        data[len - 2] ^= 0x5A;
        std::fs::write(journal_path, &data).unwrap();
    }

    let journal = DurableJournal::new(journal_path);
    let recovery_result = ExecutionOrchestrator::recover_and_start(journal);
    assert!(recovery_result.is_err(), "Journal recovery with checksum/payload corruption must fail fatally");

    let _ = std::fs::remove_file(journal_path);
}

#[test]
fn test_crash_point_recovery_after_risk_reservation() {
    let journal_path = "crash_risk.journal";
    let _ = std::fs::remove_file(journal_path);

    let order_id_str = "ORD-CRASH-1".to_string();
    let exposure = Money::new(3_000_000, "USD", 4);

    {
        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();

        let admit_event = ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
            order_id: order_id_str.clone(),
            sequence_number: 1,
            request_nonce: "NONCE-C-1".into(),
            certificate_generation: 1,
            instrument: "AAPL".into(),
            requested_quantity: 30,
        });
        gateway.process_event_transaction(vec![admit_event], 1000).unwrap();

        let reserve_event = ExecutionEvent::Intent(GatewayIntent::RiskReserved {
            order_id: order_id_str.clone(),
            notional_exposure: exposure.clone(),
        });
        gateway.process_event_transaction(vec![reserve_event], 1001).unwrap();
    }

    {
        let journal = DurableJournal::new(journal_path);
        let gateway = ExecutionOrchestrator::recover_and_start(journal)
            .expect("Gateway recovery after risk reservation crash failed");

        let snap = gateway.projected_snapshot();
        let order = snap.get(&order_id_str).expect("Order should exist after recovery");
        
        assert_eq!(order.requested_qty, 30);
        assert_eq!(order.reserved_exposure_units, exposure.units);
    }

    let _ = std::fs::remove_file(journal_path);
}

#[test]
fn test_crash_point_recovery_after_partial_fills() {
    let journal_path = "crash_fills.journal";
    let _ = std::fs::remove_file(journal_path);

    let order_id_str = "ORD-CRASH-2".to_string();
    let broker_order_id = "B-CRASH-2".to_string();
    let exposure = Money::new(10_000_000, "USD", 4);

    {
        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal).unwrap();

        gateway.process_event_transaction(vec![
            ExecutionEvent::Intent(GatewayIntent::OrderAdmitted {
                order_id: order_id_str.clone(),
                sequence_number: 1,
                request_nonce: "NONCE-C-2".into(),
                certificate_generation: 1,
                instrument: "MSFT".into(),
                requested_quantity: 100,
            })
        ], 2000).unwrap();

        gateway.process_event_transaction(vec![
            ExecutionEvent::Intent(GatewayIntent::RiskReserved {
                order_id: order_id_str.clone(),
                notional_exposure: exposure.clone(),
            })
        ], 2001).unwrap();

        gateway.mark_submission_started(&order_id_str, "IDEMP-C-2", 2002).unwrap();

        gateway.process_broker_fact(ExecutionEvent::Fact(BrokerFact::BrokerAcknowledged {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            requested_quantity: 100,
            original_exposure: exposure.clone(),
        }), 2003).unwrap();

        gateway.process_broker_fact(ExecutionEvent::Fact(BrokerFact::FillReceived {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            broker_fill_id: "FILL-C-1".into(),
            fill_quantity: 40,
            price: Money::new(100_000, "USD", 4),
            remaining_quantity: 60,
        }), 2004).unwrap();
    }

    {
        let journal = DurableJournal::new(journal_path);
        let mut gateway = ExecutionOrchestrator::recover_and_start(journal)
            .expect("Gateway recovery mid-fill failed");

        let snap_recovered = gateway.projected_snapshot();
        let order_recovered = snap_recovered.get(&order_id_str).unwrap();
        assert_eq!(order_recovered.filled_qty, 40);
        assert_eq!(order_recovered.remaining_qty, 60);

        gateway.process_broker_fact(ExecutionEvent::Fact(BrokerFact::FillReceived {
            order_id: order_id_str.clone(),
            broker_order_id: broker_order_id.clone(),
            broker_fill_id: "FILL-C-2".into(),
            fill_quantity: 60,
            price: Money::new(100_000, "USD", 4),
            remaining_quantity: 0,
        }), 2005).unwrap();

        let snap_final = gateway.projected_snapshot();
        let order_final = snap_final.get(&order_id_str).unwrap();
        assert_eq!(order_final.state, "Filled");
        assert_eq!(order_final.filled_qty, 100);
        assert_eq!(order_final.remaining_qty, 0);
    }

    let _ = std::fs::remove_file(journal_path);
}