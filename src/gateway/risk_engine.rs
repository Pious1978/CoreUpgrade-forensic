// src/gateway/risk_engine.rs

use serde_json::Value;
use std::collections::VecDeque;
use crate::pki::ActiveCertificateState;

pub struct RiskState {
    // Stores tuples of (timestamp_seconds, notional_value)
    order_history: VecDeque<(f64, f64)>, 
}

impl RiskState {
    pub fn new() -> Self {
        RiskState {
            order_history: VecDeque::new(),
        }
    }

    /// Prunes orders older than 1 second and returns the current 1-second rolling notional volume.
    pub fn get_current_velocity(&mut self, current_time: f64) -> f64 {
        while let Some(&(ts, _)) = self.order_history.front() {
            if current_time - ts > 1.0 {
                self.order_history.pop_front();
            } else {
                break;
            }
        }
        self.order_history.iter().map(|&(_, notional)| notional).sum()
    }

    pub fn record_execution(&mut self, current_time: f64, notional: f64) {
        self.order_history.push_back((current_time, notional));
    }
}

pub struct RiskEngine;

impl RiskEngine {
    pub fn authorize_execution(
        payload: &Value,
        certificate: &ActiveCertificateState,
        risk_state: &mut RiskState,
        current_time: f64,
    ) -> Result<(), String> {
        
        let account = payload.get("account").and_then(Value::as_str).unwrap();
        let strategy_hash = payload.get("strategy_hash").and_then(Value::as_str).unwrap();
        let quantity = payload.get("quantity").and_then(Value::as_f64).unwrap();
        let price = payload.get("price").and_then(Value::as_f64).unwrap();

        if !certificate.allowed_accounts.iter().any(|a| a == account) {
            return Err(format!("RISK REJECT: Account '{}' not authorized.", account));
        }

        if !certificate.allowed_strategy_hashes.iter().any(|s| s == strategy_hash) {
            return Err(format!("RISK REJECT: Strategy hash '{}' not authorized.", strategy_hash));
        }

        let notional = quantity * price;
        if notional > certificate.max_order_notional {
            return Err(format!("RISK REJECT: Order notional ({}) exceeds max ({}).", notional, certificate.max_order_notional));
        }

        let projected_velocity = risk_state.get_current_velocity(current_time) + notional;
        if projected_velocity > certificate.max_velocity_1s {
            return Err(format!("RISK REJECT: 1-second velocity limit exceeded ({} > {}).", projected_velocity, certificate.max_velocity_1s));
        }

        // Update sidecar-owned state upon successful risk authorization
        risk_state.record_execution(current_time, notional);
        
        Ok(())
    }
}