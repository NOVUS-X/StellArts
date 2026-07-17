use soroban_sdk::{contracttype, Address};

#[contracttype]
pub struct EngagementInitializedEvent {
    pub id: u64,
    pub client: Address,
    pub artisan: Address,
    pub arbitrator: Address,
    pub token: Address,
    pub material_amount: i128,
    pub labor_amount: i128,
}

#[contracttype]
pub struct FundsDepositedEvent {
    pub id: u64,
    pub client: Address,
    pub amount: i128,
    pub token: Address,
}

#[contracttype]
pub struct FundsReleasedEvent {
    pub id: u64,
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub token: Address,
}

#[contracttype]
pub struct MaterialsReleasedEvent {
    pub id: u64,
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub token: Address,
}

#[contracttype]
pub struct ReclaimedEvent {
    pub id: u64,
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub token: Address,
    pub timestamp: u64,
}

#[contracttype]
pub struct DisputeInitiatedEvent {
    pub id: u64,
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub token: Address,
    pub initiator: Address,
    pub timestamp: u64,
}

#[contracttype]
pub struct DisputeResolvedEvent {
    pub id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub client_amount: i128,
    pub artisan_amount: i128,
    pub timestamp: u64,
}

#[contracttype]
pub struct CleanupEvent {
    pub id: u64,
}
