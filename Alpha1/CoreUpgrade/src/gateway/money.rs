use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Currency(pub String);

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Money {
    pub units: i128,
    pub currency: Currency,
    pub scale: u8,
}

impl Money {
    pub fn new(units: i128, currency: &str, scale: u8) -> Self {
        Money { units, currency: Currency(currency.to_string()), scale }
    }

    pub fn zero(currency: &str, scale: u8) -> Self {
        Self::new(0, currency, scale)
    }

    pub fn checked_sub(&self, other: &Self) -> Result<Self, String> {
        if self.currency != other.currency || self.scale != other.scale {
            return Err("CRITICAL ERROR: Currency or scale mismatch in monetary operation".into());
        }
        let new_units = self.units.checked_sub(other.units)
            .ok_or("Money subtraction underflow")?;
        Ok(Money { units: new_units, currency: self.currency.clone(), scale: self.scale })
    }

    /// Exact proportional release using Floor rounding.
    pub fn calculate_incremental_release(
        original_exposure: &Money,
        cumulative_filled: u64,
        requested_qty: u64,
        previously_released: &Money,
    ) -> Result<Money, String> {
        if requested_qty == 0 { return Err("Requested quantity cannot be zero".into()); }
        if original_exposure.currency != previously_released.currency || original_exposure.scale != previously_released.scale {
            return Err("Currency or scale mismatch in risk calculation".into());
        }

        let numerator = original_exposure.units.checked_mul(cumulative_filled as i128)
            .ok_or("Money multiplication overflow")?;
        
        // Floor rounding is implicit in integer division, preserving risk conservatively.
        let cumulative_release_units = numerator / (requested_qty as i128);
        let incremental_units = cumulative_release_units.checked_sub(previously_released.units)
            .ok_or("Incremental risk release underflow")?;

        Ok(Money {
            units: incremental_units,
            currency: original_exposure.currency.clone(),
            scale: original_exposure.scale,
        })
    }
}