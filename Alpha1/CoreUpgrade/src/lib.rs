pub mod durable_file;
pub mod execution_events;
pub mod execution_orchestrator;
pub mod journal;

pub mod money {
    use serde::{Deserialize, Serialize};
    use std::ops::{Add, Sub};

    #[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
    pub struct Currency(pub String);

    #[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
    pub struct Money {
        pub units: i128,
        pub currency: Currency,
        pub scale: u32,
    }

    // Alias basis_units to units for compatibility with the journal code
    impl Money {
        pub fn basis_units(&self) -> i128 {
            self.units
        }

        pub fn new(units: i128, currency: &str, scale: u32) -> Self {
            Self {
                units,
                currency: Currency(currency.to_string()),
                scale,
            }
        }

        pub fn zero(currency: &str, scale: u32) -> Self {
            Self {
                units: 0,
                currency: Currency(currency.to_string()),
                scale,
            }
        }
    }

    impl Add for Money {
        type Output = Self;
        fn add(self, other: Self) -> Self::Output {
            Self {
                units: self.units + other.units,
                currency: self.currency,
                scale: self.scale,
            }
        }
    }

    impl Sub for Money {
        type Output = Self;
        fn sub(self, other: Self) -> Self::Output {
            Self {
                units: self.units - other.units,
                currency: self.currency,
                scale: self.scale,
            }
        }
    }
}