use std::collections::{HashMap, HashSet};
use crate::oracle::EconomicSnapshot;

pub struct MonotonicityTracker {
    history: Vec<HashMap<String, EconomicSnapshot>>,
}

impl MonotonicityTracker {
    pub fn new() -> Self {
        Self { history: Vec::new() }
    }

    pub fn record_snapshot(&mut self, current_snap: HashMap<String, EconomicSnapshot>) {
        if let Some(previous_snap) = self.history.last() {
            for (id, prev_order) in previous_snap {
                if let Some(curr_order) = current_snap.get(id) {
                    
                    // LAW 5: Observed fills can never be un-observed
                    assert!(
                        curr_order.observed_fills.is_superset(&prev_order.observed_fills),
                        "LAW 5 FATAL: Epistemic amnesia. Gateway forgot observed fills on {}", id
                    );

                    // LAW 5: Broker Identity is immutable once established
                    if prev_order.has_broker_identity {
                        assert!(
                            curr_order.has_broker_identity,
                            "LAW 5 FATAL: Broker identity was lost on {}", id
                        );
                    }
                }
            }
        }
        self.history.push(current_snap);
    }
    
    // Call this if a crash truncates the journal, rewinding our expectation of knowledge
    pub fn reset_to_crash_point(&mut self) {
        self.history.clear();
    }
}