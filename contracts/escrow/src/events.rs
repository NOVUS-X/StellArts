#![no_std]

use soroban_sdk::{contracttype, Env, Symbol};

/// The fixed first topic used for all escrow contract events.
pub fn escrow_topic(env: &Env) -> Symbol {
    Symbol::new(env, "Escrow")
}

/// A helper that builds the standardized escrow event topic tuple.
pub fn escrow_event_topics(env: &Env, event_type: EscrowEventType, engagement_id: u64) -> (Symbol, Symbol, u64) {
    (escrow_topic(env), event_type.symbol(env), engagement_id)
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum EscrowEventType {
    Initialized,
    Funded,
    Released,
    Reclaimed,
    DisputeInitiated,
    DisputeResolved,
    Cleanup,
}

impl EscrowEventType {
    pub fn symbol(&self, env: &Env) -> Symbol {
        match self {
            EscrowEventType::Initialized => Symbol::new(env, "Initialized"),
            EscrowEventType::Funded => Symbol::new(env, "Funded"),
            EscrowEventType::Released => Symbol::new(env, "Released"),
            EscrowEventType::Reclaimed => Symbol::new(env, "Reclaimed"),
            EscrowEventType::DisputeInitiated => Symbol::new(env, "DisputeInitiated"),
            EscrowEventType::DisputeResolved => Symbol::new(env, "DisputeResolved"),
            EscrowEventType::Cleanup => Symbol::new(env, "Cleanup"),
        }
    }
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EngagementInitializedEvent {
    pub id: u64,
    pub client: soroban_sdk::Address,
    pub artisan: soroban_sdk::Address,
    pub arbitrator: soroban_sdk::Address,
    pub token: soroban_sdk::Address,
    pub amount: i128,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FundsDepositedEvent {
    pub id: u64,
    pub client: soroban_sdk::Address,
    pub amount: i128,
    pub token: soroban_sdk::Address,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FundsReleasedEvent {
    pub id: u64,
    pub client: soroban_sdk::Address,
    pub artisan: soroban_sdk::Address,
    pub amount: i128,
    pub token: soroban_sdk::Address,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReclaimedEvent {
    pub id: u64,
    pub client: soroban_sdk::Address,
    pub artisan: soroban_sdk::Address,
    pub amount: i128,
    pub token: soroban_sdk::Address,
    pub timestamp: u64,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DisputeInitiatedEvent {
    pub id: u64,
    pub client: soroban_sdk::Address,
    pub artisan: soroban_sdk::Address,
    pub amount: i128,
    pub token: soroban_sdk::Address,
    pub initiator: soroban_sdk::Address,
    pub timestamp: u64,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DisputeResolvedEvent {
    pub id: u64,
    pub client: soroban_sdk::Address,
    pub artisan: soroban_sdk::Address,
    pub token: soroban_sdk::Address,
    pub client_amount: i128,
    pub artisan_amount: i128,
    pub timestamp: u64,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CleanupEvent {
    pub id: u64,
}
