use std::process::Command;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use arc_swap::ArcSwap;
use tokio::time::sleep;

// Policy thresholds for institutional time sync
const MAX_STRATUM: u32 = 3;
const MAX_ROOT_DISPERSION_SEC: f64 = 0.050;
const MAX_SYSTEM_OFFSET_SEC: f64 = 0.010;

#[derive(Clone, Debug)]
pub struct TimeSnapshot {
    pub synchronized_utc: f64,
    pub captured_monotonic: Instant,
}

pub struct NetworkSynchronizedTimeProvider {
    snapshot: ArcSwap<TimeSnapshot>,
}

impl NetworkSynchronizedTimeProvider {
    pub fn new() -> Result<Arc<Self>, String> {
        let initial_snapshot = Self::fetch_and_validate_time()?;
        
        let provider = Arc::new(Self {
            snapshot: ArcSwap::from_pointee(initial_snapshot),
        });

        // Spawn the background monitor
        let provider_clone = Arc::clone(&provider);
        tokio::spawn(async move {
            Self::background_monitor(provider_clone).await;
        });

        Ok(provider)
    }

    /// O(1) lock-free, syscall-free hot path time retrieval.
    pub fn current_utc_time(&self) -> f64 {
        let snap = self.snapshot.load();
        snap.synchronized_utc + snap.captured_monotonic.elapsed().as_secs_f64()
    }

    async fn background_monitor(provider: Arc<Self>) {
        loop {
            sleep(Duration::from_secs(10)).await;
            match Self::fetch_and_validate_time() {
                Ok(new_snapshot) => {
                    provider.snapshot.store(Arc::new(new_snapshot));
                }
                Err(e) => {
                    // In a production system, consecutive failures should trigger 
                    // a circuit breaker that halts the trading engine.
                    eprintln!("BACKGROUND TIME MONITOR WARNING: {}", e);
                }
            }
        }
    }

    fn fetch_and_validate_time() -> Result<TimeSnapshot, String> {
        let output = Command::new("chronyc")
            .arg("tracking")
            .output()
            .map_err(|e| format!("chronyc exec failed: {}", e))?;

        if !output.status.success() {
            return Err("chronyc tracking command failed".into());
        }

        let telemetry = String::from_utf8_lossy(&output.stdout);
        Self::validate_telemetry(&telemetry)?;

        let synchronized_utc = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| "System time before UNIX EPOCH")?
            .as_secs_f64();

        Ok(TimeSnapshot {
            synchronized_utc,
            captured_monotonic: Instant::now(),
        })
    }

    fn validate_telemetry(telemetry: &str) -> Result<(), String> {
        let mut leap_ok = false;
        let mut ref_present = false;

        for line in telemetry.lines() {
            let parts: Vec<&str> = line.split(':').map(|s| s.trim()).collect();
            if parts.len() != 2 { continue; }

            match parts[0] {
                "Reference ID" => {
                    if parts[1] != "00000000 ()" { ref_present = true; }
                }
                "Leap status" => {
                    if parts[1] == "Normal" { leap_ok = true; }
                }
                "Stratum" => {
                    let stratum: u32 = parts[1].parse().unwrap_or(999);
                    if stratum > MAX_STRATUM { return Err(format!("Stratum {} > {}", stratum, MAX_STRATUM)); }
                }
                "System time" => {
                    // Example: "0.000001234 seconds fast of NTP time"
                    if let Some(val_str) = parts[1].split_whitespace().next() {
                        let offset = val_str.parse::<f64>().unwrap_or(999.0).abs();
                        if offset > MAX_SYSTEM_OFFSET_SEC { return Err(format!("Offset {} > {}", offset, MAX_SYSTEM_OFFSET_SEC)); }
                    }
                }
                "Root dispersion" => {
                    if let Some(val_str) = parts[1].split_whitespace().next() {
                        let disp = val_str.parse::<f64>().unwrap_or(999.0);
                        if disp > MAX_ROOT_DISPERSION_SEC { return Err(format!("Dispersion {} > {}", disp, MAX_ROOT_DISPERSION_SEC)); }
                    }
                }
                _ => {}
            }
        }

        if !ref_present { return Err("No NTP Reference ID".into()); }
        if !leap_ok { return Err("Leap status not Normal".into()); }

        Ok(())
    }
}