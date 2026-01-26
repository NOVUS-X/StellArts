#![no_std]

// Escrow contract for StellArts
// TODO: Implement escrow contract logic
use soroban_sdk::{contracttype, Address};

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Escrow {
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub status: Status,
    pub deadline: u64
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Status {
    Pending,
    Funded,
    Released,
    Disputed
}

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Escrow(u64)
}

