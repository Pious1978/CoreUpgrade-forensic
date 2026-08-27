use std::process::Command;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use arc_swap::ArcSwap;
use tokio::time::sleep;

const MAX_STRATUM: u32 = 3;
const MAX_ROOT_DISPERSION_SEC: f64 = 0.050;
const MAX_SYSTEM_OFFSET_SEC: f64 = 0.010;
const MAX_TIME_SNAPSHOT_AGE_SEC: f64 = 30.0;
const TIME_MONITOR_INTERVAL_SEC: u64 = 10;

#[derive(Clone, Debug, PartialEq)]
pub enum TimeHealth {
    Trusted,
    Stale,
    Unsynchronized,
    Unknown,
}

#[derive(Clone, Debug)]
pub struct TimeSnapshot {
    pub synchronized_utc: f64,
    pub captured_monotonic: Instant,
    pub health: TimeHealth,
    pub uncertainty_seconds: f64,
}

pub struct NetworkSynchronizedTimeProvider {
    snapshot: ArcSwap<TimeSnapshot>,
}

impl NetworkSynchronizedTimeProvider {
    pub fn new() -> Result<Arc<Self>, String> {
        let initial_snapshot = Self::fetch_and_validate_time(true)?;
        
        let provider = Arc::new(Self {
            snapshot: ArcSwap::from_pointee(initial_snapshot),
        });

        let provider_clone = Arc::clone(&provider);
        tokio::spawn(async move {
            Self::background_monitor(provider_clone).await;
        });

        Ok(provider)
    }

    /// O(1) lock-free, syscall-free time retrieval. 
    /// Fails CLOSED if the snapshot is stale or unsynchronized.
    pub fn current_utc_time(&self) -> Result<f64, String> {
        let snap = self.snapshot.load();
        
        if snap.health != TimeHealth::Trusted {
            return Err(format!("CRITICAL ERROR: Time is not trusted (State: {:?})", snap.health));
        }

        let elapsed = snap.captured_monotonic.elapsed().as_secs_f64();
        if elapsed > MAX_TIME_SNAPSHOT_AGE_SEC {
            return Err(format!(
                "CRITICAL ERROR: Time snapshot is dangerously stale ({}s > {}s). Failing closed.", 
                elapsed, MAX_TIME_SNAPSHOT_AGE_SEC
            ));
        }

        Ok(snap.synchronized_utc + elapsed)
    }

    async fn background_monitor(provider: Arc<Self>) {
        loop {
            sleep(Duration::from_secs(TIME_MONITOR_INTERVAL_SEC)).await;
            match Self::fetch_and_validate_time(false) {
                Ok(new_snapshot) => {
                    provider.snapshot.store(Arc::new(new_snapshot));
                }
                Err(e) => {
                    eprintln!("BACKGROUND TIME MONITOR FAULT: {}", e);
                    // Publish an explicitly unsynchronized snapshot to trigger hot-path failure
                    provider.snapshot.store(Arc::new(TimeSnapshot {
                        synchronized_utc: 0.0,
                        captured_monotonic: Instant::now(),
                        health: TimeHealth::Unsynchronized,
                        uncertainty_seconds: f64::MAX,
                    }));
                }
            }
        }
    }

    fn fetch_and_validate_time(is_boot: bool) -> Result<TimeSnapshot, String> {
        let output = Command::new("chronyc")
            .arg("tracking")
            .output()
            .map_err(|e| format!("chronyc exec failed: {}", e))?;

        if !output.status.success() {
            return Err("chronyc tracking command failed".into());
        }

        let telemetry = String::from_utf8_lossy(&output.stdout);
        let dispersion = Self::validate_telemetry(&telemetry)?;

        let synchronized_utc = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| "System time before UNIX EPOCH")?
            .as_secs_f64();

        Ok(TimeSnapshot {
            synchronized_utc,
            captured_monotonic: Instant::now(),
            health: TimeHealth::Trusted,
            uncertainty_seconds: dispersion,
        })
    }

    fn validate_telemetry(telemetry: &str) -> Result<f64, String> {
        let mut leap_ok = false;
        let mut ref_present = false;
        let mut stratum_ok = false;
        let mut offset_ok = false;
        let mut dispersion_val: Option<f64> = None;

        for line in telemetry.lines() {
            // Safe parsing: only split on the FIRST colon
            if let Some((key, val)) = line.split_once(':') {
                let key = key.trim();
                let val = val.trim();

                match key {
                    "Reference ID" => {
                        if val != "00000000 ()" { ref_present = true; }
                    }
                    "Leap status" => {
                        if val == "Normal" { leap_ok = true; }
                    }
                    "Stratum" => {
                        if let Ok(stratum) = val.parse::<u32>() {
                            if stratum <= MAX_STRATUM { stratum_ok = true; }
                        }
                    }
                    "System time" => {
                        if let Some(val_str) = val.split_whitespace().next() {
                            if let Ok(offset) = val_str.parse::<f64>() {
                                if offset.abs() <= MAX_SYSTEM_OFFSET_SEC { offset_ok = true; }
                            }
                        }
                    }
                    "Root dispersion" => {
                        if let Some(val_str) = val.split_whitespace().next() {
                            if let Ok(disp) = val_str.parse::<f64>() {
                                if disp <= MAX_ROOT_DISPERSION_SEC { dispersion_val = Some(disp); }
                            }
                        }
                    }
                    _ => {}
                }
            }
        }

        if !ref_present { return Err("NTP Reference ID missing or invalid".into()); }
        if !leap_ok { return Err("Leap status not Normal".into()); }
        if !stratum_ok { return Err("Stratum missing or exceeded limit".into()); }
        if !offset_ok { return Err("System offset missing or exceeded limit".into()); }
        
        dispersion_val.ok_or_else(|| "Root dispersion missing or exceeded limit".into())
    }
}