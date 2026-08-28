#![no_std]

use soroban_sdk::{contracttype, Address, Env, Symbol};

// Standard Contract Event Domain Topics
pub const TOPIC_DOMAIN_ESCROW: &str = "Escrow";
pub const TOPIC_DOMAIN_TREASURY: &str = "Treasury";

// Standard Event Action Topics
pub const ACTION_INITIALIZED: &str = "Initialized";
pub const ACTION_FUNDED: &str = "Funded";
pub const ACTION_MATERIALS_RELEASED: &str = "MaterialsReleased";
pub const ACTION_RELEASED: &str = "Released";
pub const ACTION_MILESTONE_RELEASED: &str = "MilestoneReleased";
pub const ACTION_RECLAIMED: &str = "Reclaimed";
pub const ACTION_DISPUTED: &str = "Disputed";
pub const ACTION_RESOLVED: &str = "Resolved";
pub const ACTION_FEE_COLLECTED: &str = "FeeCollected";
pub const ACTION_CONFIGURED: &str = "Configured";
pub const ACTION_CLEANED_UP: &str = "CleanedUp";

// ============================================================================
// Event Data Payload Structures
// ============================================================================

/// Emitted when a new escrow engagement is created.
/// Topics: ["Escrow", "Initialized", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EngagementInitializedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub arbitrator: Address,
    pub token: Address,
    pub material_amount: i128,
    pub labor_amount: i128,
    pub deadline: u64,
}

/// Emitted when funds are deposited into escrow.
/// Topics: ["Escrow", "Funded", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FundsDepositedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub token: Address,
    pub amount: i128,
}

/// Emitted when material funds are released upfront to the artisan.
/// Topics: ["Escrow", "MaterialsReleased", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MaterialsReleasedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub amount: i128,
}

/// Emitted when final escrow funds are released to the artisan.
/// Topics: ["Escrow", "Released", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FundsReleasedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub amount: i128,
}

/// Emitted when a specific milestone payout is released to the artisan.
/// Topics: ["Escrow", "MilestoneReleased", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MilestoneReleasedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub milestone_index: u32,
    pub percentage: u32,
    pub amount: i128,
}

/// Emitted when an expired/unfulfilled escrow is reclaimed by the client.
/// Topics: ["Escrow", "Reclaimed", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReclaimedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub amount: i128,
    pub timestamp: u64,
}

/// Emitted when a dispute is opened on an active escrow.
/// Topics: ["Escrow", "Disputed", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DisputeInitiatedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub amount: i128,
    pub initiator: Address,
    pub timestamp: u64,
}

/// Emitted when an arbitrator or DAO jury resolves an escrow dispute.
/// Topics: ["Escrow", "Resolved", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DisputeResolvedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub client_amount: i128,
    pub artisan_amount: i128,
    pub resolver: Address,
    pub timestamp: u64,
}

/// Emitted when protocol fee is deducted and transferred to treasury.
/// Topics: ["Escrow", "FeeCollected", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FeeCollectedEvent {
    pub engagement_id: u64,
    pub treasury: Address,
    pub token: Address,
    pub fee_amount: i128,
}

/// Emitted when the protocol treasury configuration is initialized/updated.
/// Topics: ["Treasury", "Configured"]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TreasuryConfiguredEvent {
    pub treasury: Address,
    pub fee_basis_points: u32,
}

/// Emitted when a finalized escrow is cleaned up from storage.
/// Topics: ["Escrow", "CleanedUp", engagement_id]
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EscrowCleanedUpEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub timestamp: u64,
}

// ============================================================================
// Standardized Event Publishing Helper Functions
// ============================================================================

/// Emits standardized `["Escrow", "Initialized", engagement_id]` event.
pub fn emit_initialized(
    env: &Env,
    engagement_id: u64,
    client: Address,
    artisan: Address,
    arbitrator: Address,
    token: Address,
    material_amount: i128,
    labor_amount: i128,
    deadline: u64,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_INITIALIZED),
        engagement_id,
    );
    let payload = EngagementInitializedEvent {
        engagement_id,
        client,
        artisan,
        arbitrator,
        token,
        material_amount,
        labor_amount,
        deadline,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "Funded", engagement_id]` event.
pub fn emit_funded(
    env: &Env,
    engagement_id: u64,
    client: Address,
    token: Address,
    amount: i128,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_FUNDED),
        engagement_id,
    );
    let payload = FundsDepositedEvent {
        engagement_id,
        client,
        token,
        amount,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "MaterialsReleased", engagement_id]` event.
pub fn emit_materials_released(
    env: &Env,
    engagement_id: u64,
    client: Address,
    artisan: Address,
    token: Address,
    amount: i128,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_MATERIALS_RELEASED),
        engagement_id,
    );
    let payload = MaterialsReleasedEvent {
        engagement_id,
        client,
        artisan,
        token,
        amount,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "Released", engagement_id]` event.
pub fn emit_released(
    env: &Env,
    engagement_id: u64,
    client: Address,
    artisan: Address,
    token: Address,
    amount: i128,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_RELEASED),
        engagement_id,
    );
    let payload = FundsReleasedEvent {
        engagement_id,
        client,
        artisan,
        token,
        amount,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "MilestoneReleased", engagement_id]` event.
pub fn emit_milestone_released(
    env: &Env,
    engagement_id: u64,
    client: Address,
    artisan: Address,
    token: Address,
    milestone_index: u32,
    percentage: u32,
    amount: i128,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_MILESTONE_RELEASED),
        engagement_id,
    );
    let payload = MilestoneReleasedEvent {
        engagement_id,
        client,
        artisan,
        token,
        milestone_index,
        percentage,
        amount,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "Reclaimed", engagement_id]` event.
pub fn emit_reclaimed(
    env: &Env,
    engagement_id: u64,
    client: Address,
    artisan: Address,
    token: Address,
    amount: i128,
    timestamp: u64,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_RECLAIMED),
        engagement_id,
    );
    let payload = ReclaimedEvent {
        engagement_id,
        client,
        artisan,
        token,
        amount,
        timestamp,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "Disputed", engagement_id]` event.
pub fn emit_disputed(
    env: &Env,
    engagement_id: u64,
    client: Address,
    artisan: Address,
    token: Address,
    amount: i128,
    initiator: Address,
    timestamp: u64,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_DISPUTED),
        engagement_id,
    );
    let payload = DisputeInitiatedEvent {
        engagement_id,
        client,
        artisan,
        token,
        amount,
        initiator,
        timestamp,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "Resolved", engagement_id]` event.
pub fn emit_resolved(
    env: &Env,
    engagement_id: u64,
    client: Address,
    artisan: Address,
    token: Address,
    client_amount: i128,
    artisan_amount: i128,
    resolver: Address,
    timestamp: u64,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_RESOLVED),
        engagement_id,
    );
    let payload = DisputeResolvedEvent {
        engagement_id,
        client,
        artisan,
        token,
        client_amount,
        artisan_amount,
        resolver,
        timestamp,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "FeeCollected", engagement_id]` event.
pub fn emit_fee_collected(
    env: &Env,
    engagement_id: u64,
    treasury: Address,
    token: Address,
    fee_amount: i128,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_FEE_COLLECTED),
        engagement_id,
    );
    let payload = FeeCollectedEvent {
        engagement_id,
        treasury,
        token,
        fee_amount,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Treasury", "Configured"]` event.
pub fn emit_treasury_configured(
    env: &Env,
    treasury: Address,
    fee_basis_points: u32,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_TREASURY),
        Symbol::new(env, ACTION_CONFIGURED),
    );
    let payload = TreasuryConfiguredEvent {
        treasury,
        fee_basis_points,
    };
    env.events().publish(topics, payload);
}

/// Emits standardized `["Escrow", "CleanedUp", engagement_id]` event.
pub fn emit_cleaned_up(
    env: &Env,
    engagement_id: u64,
    client: Address,
    timestamp: u64,
) {
    let topics = (
        Symbol::new(env, TOPIC_DOMAIN_ESCROW),
        Symbol::new(env, ACTION_CLEANED_UP),
        engagement_id,
    );
    let payload = EscrowCleanedUpEvent {
        engagement_id,
        client,
        timestamp,
    };
    env.events().publish(topics, payload);
}
