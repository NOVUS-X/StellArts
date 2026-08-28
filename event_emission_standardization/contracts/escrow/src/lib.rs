#![no_std]

pub mod events;

use soroban_sdk::{contract, contractimpl, contracttype, token, vec, Address, Env, Symbol, Vec};

// Protocol fee cap — 1000 bps = 10%. Prevents admin from misconfiguring
// an unreasonably high fee; adjust if product requirements change.
const MAX_FEE_BPS: u32 = 1_000;

// Max share of the protocol fee that may be allocated to jury rewards,
// out of 10_000 bps. 100% of the fee may be routed to the jury pool.
const MAX_JURY_REWARD_BPS: u32 = 10_000;

// TTL constants for persistent storage (in ledgers)
// Note: Each ledger is approximately 5 seconds
const ESCROW_TTL: u32 = 1_036_800; // ~60 days
const NEXT_ID_TTL: u32 = 6_220_800; // ~1 year
const TTL_THRESHOLD: u32 = 17_280; // ~1 day - triggers extension when TTL drops below this
const GRACE_PERIOD: u64 = 86_400; // 24 hours in seconds - artisan protection window after deadline

/// Multi-sig configuration for large escrow payments.
/// When `required_signers` is non-empty, `release` requires that at least
/// `threshold` of those signers have called `multisig_approve` before funds
/// can be transferred to the artisan.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MultiSigConfig {
    /// Addresses that are allowed to sign off on the release.
    pub required_signers: Vec<Address>,
    /// Number of approvals needed before release is permitted.
    pub threshold: u32,
}

/// Protocol fee configuration. `fee_basis_points` is out of 10_000
/// (e.g. 250 = 2.5%). Fee is only applied to artisan payouts, never
/// to client refunds.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TreasuryConfig {
    pub treasury_address: Address,
    pub fee_basis_points: u32,
}

/// Tracks which signers have already approved a multi-sig release.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MultiSigApprovals {
    pub approvals: Vec<Address>,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Escrow {
    pub client: Address,
    pub artisan: Address,
    pub arbitrator: Address,
    pub token: Address,
    pub material_amount: i128,
    pub labor_amount: i128,
    pub status: Status,
    pub deadline: u64,
    pub materials_released: bool,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DeadlineExtension {
    pub new_deadline: u64,
    pub proposer: Address,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Status {
    Pending,
    Funded,
    InProgress,
    Released,
    Refunded, // added for reclaimed/returned escrows
    Disputed,
    Resolved, // dispute resolved with split distribution
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EarlyReclaimApproval {
    pub proposer: Address,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DataKey {
    Escrow(u64),
    DeadlineExtension(u64),
    EarlyReclaim(u64),
    MultiSigConfig(u64),
    MultiSigApprovals(u64),
    /// Ordered milestone percentages (must sum to 100 when present).
    Milestones(u64),
    /// Index of the next milestone eligible for release.
    NextMilestone(u64),
    /// Cumulative amount already paid out via `release_milestone`.
    MilestoneReleased(u64),
    NextId,
    Oracle,
    Admin,
    IsPaused,
    Lock,
    Treasury,
    /// DAO dispute resolution contract authorized to resolve disputed escrows
    /// on behalf of a selected jury (`resolve_dispute_dao`).
    DisputeResolver,
    /// Portion of the protocol fee (out of 10_000) allocated to jury rewards.
    JuryRewardBps,
}

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowContract {
    fn check_and_set_lock(env: &Env) {
        let is_locked: bool = env
            .storage()
            .instance()
            .get(&DataKey::Lock)
            .unwrap_or(false);
        if is_locked {
            panic!("Reentrancy detected");
        }
        env.storage().instance().set(&DataKey::Lock, &true);
    }

    fn clear_lock(env: &Env) {
        env.storage().instance().set(&DataKey::Lock, &false);
    }

    pub fn init_admin(env: Env, admin: Address) {
        if env.storage().instance().has(&DataKey::Admin) {
            panic!("Admin already set");
        }
        env.storage().instance().set(&DataKey::Admin, &admin);
    }

    pub fn is_paused(env: &Env) -> bool {
        env.storage()
            .instance()
            .get(&DataKey::IsPaused)
            .unwrap_or(false)
    }

    pub fn pause(env: Env) {
        let admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .expect("Admin not set");
        admin.require_auth();
        env.storage().instance().set(&DataKey::IsPaused, &true);
    }

    /// amount * bps / 10_000, floored. Floor rounding guarantees
    /// fee + remainder == amount exactly — no dust is ever left behind.
    fn calculate_fee(amount: i128, fee_bps: u32) -> i128 {
        amount
            .checked_mul(fee_bps as i128)
            .expect("fee calculation overflow")
            / 10_000
    }

    fn get_treasury_config(env: &Env) -> Option<TreasuryConfig> {
        env.storage().persistent().get(&DataKey::Treasury)
    }

    fn has_milestones(env: &Env, engagement_id: u64) -> bool {
        env.storage()
            .persistent()
            .has(&DataKey::Milestones(engagement_id))
    }

    fn validate_milestones(milestones: &Vec<u32>) {
        if milestones.is_empty() {
            return;
        }
        let mut total: u32 = 0;
        for pct in milestones.iter() {
            if pct == 0 {
                panic!("Milestone percentage must be greater than zero");
            }
            total = total
                .checked_add(pct)
                .expect("Milestone percentage sum overflow");
        }
        if total != 100 {
            panic!("Milestone percentages must sum to exactly 100");
        }
    }

    fn pay_artisan_with_optional_fee(
        env: &Env,
        engagement_id: u64,
        escrow: &Escrow,
        token: &Address,
        transfer_amount: i128,
    ) {
        let token_client = token::Client::new(env, token);
        if let Some(cfg) = Self::get_treasury_config(env) {
            let fee = Self::calculate_fee(transfer_amount, cfg.fee_basis_points);
            let artisan_payout = transfer_amount - fee;

            if fee > 0 {
                token_client.transfer(&env.current_contract_address(), &cfg.treasury_address, &fee);
                // Standardized FeeCollected event emission
                events::emit_fee_collected(
                    env,
                    engagement_id,
                    cfg.treasury_address,
                    escrow.token.clone(),
                    fee,
                );
            }
            token_client.transfer(
                &env.current_contract_address(),
                &escrow.artisan,
                &artisan_payout,
            );
        } else {
            token_client.transfer(
                &env.current_contract_address(),
                &escrow.artisan,
                &transfer_amount,
            );
        }
    }

    pub fn unpause(env: Env) {
        let admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .expect("Admin not set");
        admin.require_auth();
        env.storage().instance().set(&DataKey::IsPaused, &false);
    }

    pub fn set_arbitrator(env: Env, arbitrator: Address) {
        env.storage().instance().set(&DataKey::Admin, &arbitrator);
    }

    pub fn set_oracle(env: Env, oracle: Address) {
        env.storage().persistent().set(&DataKey::Oracle, &oracle);
    }

    pub fn get_oracle(env: Env) -> Option<Address> {
        env.storage().persistent().get(&DataKey::Oracle)
    }

    pub fn initialize(
        env: Env,
        client: Address,
        artisan: Address,
        arbitrator: Address,
        token: Address,
        material_amount: i128,
        labor_amount: i128,
        deadline: u64,
        multisig_signers: Vec<Address>,
        multisig_threshold: u32,
        milestones: Vec<u32>,
    ) -> u64 {
        assert!(!Self::is_paused(&env), "contract is paused");
        if client == artisan {
            panic!("Client and artisan cannot be the same address");
        }

        let total_amount = material_amount + labor_amount;
        if total_amount <= 0 {
            panic!("Total amount must be greater than zero");
        }

        if material_amount < 0 || labor_amount < 0 {
            panic!("Amount cannot be negative");
        }

        let current_time = env.ledger().timestamp();
        if deadline <= current_time {
            panic!("Deadline must be in the future");
        }

        if !multisig_signers.is_empty() {
            if multisig_threshold == 0 {
                panic!("Multi-sig threshold must be greater than zero");
            }
            if multisig_threshold > multisig_signers.len() {
                panic!("Multi-sig threshold cannot exceed number of signers");
            }
        } else if multisig_threshold > 0 {
            panic!("Cannot set multi-sig threshold without signers");
        }

        Self::validate_milestones(&milestones);

        let mut engagement_id: u64 = env
            .storage()
            .persistent()
            .get(&DataKey::NextId)
            .unwrap_or(1);

        let current_id = engagement_id;
        engagement_id += 1;
        env.storage().persistent().set(&DataKey::NextId, &engagement_id);
        env.storage()
            .persistent()
            .extend_ttl(&DataKey::NextId, TTL_THRESHOLD, NEXT_ID_TTL);

        let engagement_id = current_id;

        if !multisig_signers.is_empty() {
            let cfg = MultiSigConfig {
                required_signers: multisig_signers,
                threshold: multisig_threshold,
            };
            let cfg_key = DataKey::MultiSigConfig(engagement_id);
            env.storage().persistent().set(&cfg_key, &cfg);
            env.storage()
                .persistent()
                .extend_ttl(&cfg_key, TTL_THRESHOLD, ESCROW_TTL);
        }

        if !milestones.is_empty() {
            let m_key = DataKey::Milestones(engagement_id);
            let next_key = DataKey::NextMilestone(engagement_id);
            let rel_key = DataKey::MilestoneReleased(engagement_id);
            env.storage().persistent().set(&m_key, &milestones);
            env.storage().persistent().set(&next_key, &0u32);
            env.storage().persistent().set(&rel_key, &0i128);
            env.storage()
                .persistent()
                .extend_ttl(&m_key, TTL_THRESHOLD, ESCROW_TTL);
            env.storage()
                .persistent()
                .extend_ttl(&next_key, TTL_THRESHOLD, ESCROW_TTL);
            env.storage()
                .persistent()
                .extend_ttl(&rel_key, TTL_THRESHOLD, ESCROW_TTL);
        }

        let escrow = Escrow {
            client: client.clone(),
            artisan: artisan.clone(),
            arbitrator: arbitrator.clone(),
            token: token.clone(),
            material_amount,
            labor_amount,
            status: Status::Pending,
            deadline,
            materials_released: false,
        };

        let escrow_key = DataKey::Escrow(engagement_id);
        env.storage().persistent().set(&escrow_key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&escrow_key, TTL_THRESHOLD, ESCROW_TTL);

        // Standardized Event Emission
        events::emit_initialized(
            &env,
            engagement_id,
            client,
            artisan,
            arbitrator,
            token,
            material_amount,
            labor_amount,
            deadline,
        );

        engagement_id
    }

    pub fn deposit(env: Env, engagement_id: u64, token: Address) {
        assert!(!Self::is_paused(&env), "contract is paused");
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .unwrap_or_else(|| panic!("Escrow not found for engagement {}", engagement_id));

        if token != escrow.token {
            panic!("Token does not match the initialized token for this engagement");
        }

        let current_time = env.ledger().timestamp();
        if current_time > escrow.deadline {
            panic!("Deadline has passed; cannot deposit into this escrow");
        }

        escrow.client.require_auth();

        if escrow.status != Status::Pending {
            panic!("Escrow must be in Pending status to deposit funds");
        }

        let total = escrow.material_amount + escrow.labor_amount;
        let token_client = token::Client::new(&env, &token);
        token_client.transfer(&escrow.client, &env.current_contract_address(), &total);

        escrow.status = Status::Funded;

        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        // Standardized Event Emission
        events::emit_funded(&env, engagement_id, escrow.client, escrow.token, total);
    }

    pub fn release_materials(env: Env, engagement_id: u64, token: Address, caller: Address) {
        assert!(!Self::is_paused(&env), "contract is paused");
        caller.require_auth();

        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        if caller != escrow.client && caller != escrow.artisan {
            panic!("Only the client or artisan can release material funds");
        }

        if token != escrow.token {
            panic!("Token does not match the initialized token for this engagement");
        }

        let current_time = env.ledger().timestamp();
        if current_time > escrow.deadline {
            panic!("Deadline has passed; cannot release material funds");
        }

        if escrow.status != Status::Funded {
            panic!("Escrow is not funded");
        }

        if escrow.materials_released {
            panic!("Material funds have already been released");
        }

        if escrow.material_amount <= 0 {
            panic!("No material funds allocated for this engagement");
        }

        let token_client = token::Client::new(&env, &token);
        token_client.transfer(
            &env.current_contract_address(),
            &escrow.artisan,
            &escrow.material_amount,
        );

        escrow.materials_released = true;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        // Standardized Event Emission
        events::emit_materials_released(
            &env,
            engagement_id,
            escrow.client,
            escrow.artisan,
            escrow.token,
            escrow.material_amount,
        );
    }

    pub fn release(env: Env, engagement_id: u64, token: Address) {
        assert!(!Self::is_paused(&env), "contract is paused");
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        if token != escrow.token {
            panic!("Token does not match the initialized token for this engagement");
        }

        escrow.client.require_auth();

        let current_time = env.ledger().timestamp();
        if current_time > escrow.deadline {
            panic!("Deadline has passed; cannot release funds");
        }

        if escrow.status != Status::Funded && escrow.status != Status::InProgress {
            panic!("Escrow is not funded or in progress");
        }

        if Self::has_milestones(&env, engagement_id) {
            panic!("Use release_milestone for milestone-based escrows");
        }

        let cfg_key = DataKey::MultiSigConfig(engagement_id);
        if let Some(cfg) = env
            .storage()
            .persistent()
            .get::<DataKey, MultiSigConfig>(&cfg_key)
        {
            let approvals_key = DataKey::MultiSigApprovals(engagement_id);
            let approvals: MultiSigApprovals = env
                .storage()
                .persistent()
                .get(&approvals_key)
                .unwrap_or(MultiSigApprovals {
                    approvals: vec![&env],
                });
            if approvals.approvals.len() < cfg.threshold {
                panic!("Multi-sig threshold not met; more approvals required before release");
            }
            env.storage().persistent().remove(&approvals_key);
        }

        Self::check_and_set_lock(&env);

        let transfer_amount = if escrow.materials_released {
            escrow.labor_amount
        } else {
            escrow.material_amount + escrow.labor_amount
        };

        Self::pay_artisan_with_optional_fee(&env, engagement_id, &escrow, &token, transfer_amount);

        escrow.status = Status::Released;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        // Standardized Event Emission
        events::emit_released(
            &env,
            engagement_id,
            escrow.client,
            escrow.artisan,
            escrow.token,
            transfer_amount,
        );

        Self::clear_lock(&env);
    }

    pub fn release_milestone(env: Env, engagement_id: u64, token: Address) {
        assert!(!Self::is_paused(&env), "contract is paused");
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        if token != escrow.token {
            panic!("Token does not match the initialized token for this engagement");
        }

        escrow.client.require_auth();

        let current_time = env.ledger().timestamp();
        if current_time > escrow.deadline {
            panic!("Deadline has passed; cannot release funds");
        }

        if escrow.status != Status::Funded && escrow.status != Status::InProgress {
            panic!("Escrow is not funded or in progress");
        }

        let milestones_key = DataKey::Milestones(engagement_id);
        let milestones: Vec<u32> = env
            .storage()
            .persistent()
            .get(&milestones_key)
            .expect("Engagement does not have milestones configured");

        let next_key = DataKey::NextMilestone(engagement_id);
        let next_index: u32 = env
            .storage()
            .persistent()
            .get(&next_key)
            .unwrap_or(0);

        if next_index >= milestones.len() {
            panic!("All milestones have already been released");
        }

        let percentage = milestones.get(next_index).unwrap();
        let total_budget = escrow.material_amount + escrow.labor_amount;
        let is_last = next_index + 1 == milestones.len();

        let rel_key = DataKey::MilestoneReleased(engagement_id);
        let already_released: i128 = env
            .storage()
            .persistent()
            .get(&rel_key)
            .unwrap_or(0);

        let transfer_amount = if is_last {
            total_budget - already_released
        } else {
            (total_budget * percentage as i128) / 100
        };

        Self::check_and_set_lock(&env);

        Self::pay_artisan_with_optional_fee(&env, engagement_id, &escrow, &token, transfer_amount);

        let new_released = already_released + transfer_amount;
        env.storage().persistent().set(&rel_key, &new_released);
        env.storage().persistent().set(&next_key, &(next_index + 1));
        env.storage()
            .persistent()
            .extend_ttl(&rel_key, TTL_THRESHOLD, ESCROW_TTL);
        env.storage()
            .persistent()
            .extend_ttl(&next_key, TTL_THRESHOLD, ESCROW_TTL);
        env.storage()
            .persistent()
            .extend_ttl(&milestones_key, TTL_THRESHOLD, ESCROW_TTL);

        if is_last {
            escrow.status = Status::Released;
        }

        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        // Standardized Event Emission
        events::emit_milestone_released(
            &env,
            engagement_id,
            escrow.client,
            escrow.artisan,
            escrow.token,
            next_index,
            percentage,
            transfer_amount,
        );

        Self::clear_lock(&env);
    }

    pub fn get_milestones(env: Env, engagement_id: u64) -> Vec<u32> {
        env.storage()
            .persistent()
            .get(&DataKey::Milestones(engagement_id))
            .unwrap_or(vec![&env])
    }

    pub fn get_next_milestone(env: Env, engagement_id: u64) -> u32 {
        env.storage()
            .persistent()
            .get(&DataKey::NextMilestone(engagement_id))
            .unwrap_or(0)
    }

    pub fn multisig_approve(env: Env, engagement_id: u64, signer: Address) {
        assert!(!Self::is_paused(&env), "contract is paused");
        let key = DataKey::Escrow(engagement_id);
        let escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        signer.require_auth();

        let cfg: MultiSigConfig = env
            .storage()
            .persistent()
            .get(&DataKey::MultiSigConfig(engagement_id))
            .expect("Escrow does not have multi-sig enabled");

        let mut is_allowed = false;
        for s in cfg.required_signers.iter() {
            if s == signer {
                is_allowed = true;
                break;
            }
        }
        if !is_allowed {
            panic!("Signer is not in the multi-sig required signers list");
        }

        if escrow.status != Status::Funded && escrow.status != Status::InProgress {
            panic!("Escrow must be Funded or InProgress to approve");
        }

        let approvals_key = DataKey::MultiSigApprovals(engagement_id);
        let mut approvals: MultiSigApprovals = env
            .storage()
            .persistent()
            .get(&approvals_key)
            .unwrap_or(MultiSigApprovals {
                approvals: vec![&env],
            });

        for existing in approvals.approvals.iter() {
            if existing == signer {
                panic!("Signer has already approved this escrow");
            }
        }

        approvals.approvals.push_back(signer);
        env.storage().persistent().set(&approvals_key, &approvals);
        env.storage()
            .persistent()
            .extend_ttl(&approvals_key, TTL_THRESHOLD, ESCROW_TTL);
    }

    pub fn reclaim(env: Env, engagement_id: u64, token: Address) -> bool {
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        escrow.client.require_auth();

        if escrow.status != Status::Funded {
            panic!("Escrow must be Funded to reclaim");
        }

        let current_time = env.ledger().timestamp();
        if current_time <= escrow.deadline {
            panic!("Deadline has not passed; cannot reclaim yet");
        }

        let grace_deadline = escrow.deadline + GRACE_PERIOD;
        if current_time <= grace_deadline {
            let early_reclaim_key = DataKey::EarlyReclaim(engagement_id);
            let has_early_approval: bool = env
                .storage()
                .persistent()
                .get::<DataKey, bool>(&early_reclaim_key)
                .unwrap_or(false);

            if !has_early_approval {
                panic!("Grace period has not passed; both parties must approve early reclaim");
            }

            env.storage().persistent().remove(&early_reclaim_key);
        }

        if token != escrow.token {
            panic!("Token does not match the initialized token for this engagement");
        }

        Self::check_and_set_lock(&env);
        let refund_amount = Self::remaining_escrow_balance(&env, engagement_id, &escrow);
        if refund_amount <= 0 {
            panic!("No funds remaining to reclaim");
        }

        let token_client = token::Client::new(&env, &token);
        token_client.transfer(
            &env.current_contract_address(),
            &escrow.client,
            &refund_amount,
        );

        escrow.status = Status::Refunded;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        let current_time = env.ledger().timestamp();
        // Standardized Event Emission
        events::emit_reclaimed(
            &env,
            engagement_id,
            escrow.client,
            escrow.artisan,
            escrow.token,
            refund_amount,
            current_time,
        );

        Self::clear_lock(&env);

        true
    }

    fn remaining_escrow_balance(env: &Env, engagement_id: u64, escrow: &Escrow) -> i128 {
        let total = escrow.material_amount + escrow.labor_amount;
        if Self::has_milestones(env, engagement_id) {
            let rel_key = DataKey::MilestoneReleased(engagement_id);
            let released: i128 = env.storage().persistent().get(&rel_key).unwrap_or(0);
            total - released
        } else if escrow.materials_released {
            escrow.labor_amount
        } else {
            total
        }
    }

    pub fn set_treasury(env: Env, admin: Address, treasury_address: Address, fee_basis_points: u32) {
        let stored_admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .expect("Admin not set");
        if admin != stored_admin {
            panic!("Only admin can configure treasury");
        }
        admin.require_auth();

        if fee_basis_points > MAX_FEE_BPS {
            panic!("fee_basis_points exceeds maximum allowed (10%)");
        }

        let cfg = TreasuryConfig {
            treasury_address: treasury_address.clone(),
            fee_basis_points,
        };
        env.storage().persistent().set(&DataKey::Treasury, &cfg);
        env.storage()
            .persistent()
            .extend_ttl(&DataKey::Treasury, TTL_THRESHOLD, NEXT_ID_TTL);

        // Standardized Event Emission
        events::emit_treasury_configured(&env, treasury_address, fee_basis_points);
    }

    pub fn get_treasury(env: Env) -> Option<TreasuryConfig> {
        Self::get_treasury_config(&env)
    }

    pub fn set_dispute_resolver(env: Env, admin: Address, resolver: Address) {
        let stored_admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .expect("Admin not set");
        if admin != stored_admin {
            panic!("Only admin can configure the dispute resolver");
        }
        admin.require_auth();

        env.storage()
            .persistent()
            .set(&DataKey::DisputeResolver, &resolver);
        env.storage().persistent().extend_ttl(
            &DataKey::DisputeResolver,
            TTL_THRESHOLD,
            NEXT_ID_TTL,
        );
    }

    pub fn get_dispute_resolver(env: Env) -> Option<Address> {
        env.storage().persistent().get(&DataKey::DisputeResolver)
    }

    pub fn set_jury_reward_bps(env: Env, admin: Address, bps: u32) {
        let stored_admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .expect("Admin not set");
        if admin != stored_admin {
            panic!("Only admin can configure jury rewards");
        }
        admin.require_auth();

        if bps > MAX_JURY_REWARD_BPS {
            panic!("jury_reward_bps exceeds maximum allowed");
        }

        env.storage()
            .persistent()
            .set(&DataKey::JuryRewardBps, &bps);
        env.storage()
            .persistent()
            .extend_ttl(&DataKey::JuryRewardBps, TTL_THRESHOLD, NEXT_ID_TTL);
    }

    pub fn get_jury_reward_bps(env: Env) -> u32 {
        env.storage()
            .persistent()
            .get(&DataKey::JuryRewardBps)
            .unwrap_or(0)
    }

    pub fn get_remaining_balance(env: Env, engagement_id: u64) -> i128 {
        let escrow: Escrow = env
            .storage()
            .persistent()
            .get(&DataKey::Escrow(engagement_id))
            .expect("Escrow not found");
        Self::remaining_escrow_balance(&env, engagement_id, &escrow)
    }

    pub fn resolve_dispute_dao(
        env: Env,
        engagement_id: u64,
        client_amount: i128,
        artisan_amount: i128,
        token: Address,
    ) -> i128 {
        assert!(!Self::is_paused(&env), "contract is paused");
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        let resolver: Address = env
            .storage()
            .persistent()
            .get(&DataKey::DisputeResolver)
            .expect("Dispute resolver not set");
        resolver.require_auth();

        if escrow.status != Status::Disputed {
            panic!("Escrow must be in Disputed status to resolve");
        }

        if client_amount < 0 || artisan_amount < 0 {
            panic!("Distribution amounts must be non-negative");
        }

        let remaining = Self::remaining_escrow_balance(&env, engagement_id, &escrow);
        if client_amount + artisan_amount != remaining {
            panic!("Distribution amounts must equal the remaining escrowed amount");
        }

        if token != escrow.token {
            panic!("Token does not match the initialized token for this engagement");
        }

        Self::check_and_set_lock(&env);

        if artisan_amount == 0 {
            escrow.status = Status::Refunded;
        } else if client_amount == 0 {
            escrow.status = Status::Released;
        } else {
            escrow.status = Status::Resolved;
        }

        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        let current_time = env.ledger().timestamp();
        // Standardized Event Emission
        events::emit_resolved(
            &env,
            engagement_id,
            escrow.client.clone(),
            escrow.artisan.clone(),
            escrow.token.clone(),
            client_amount,
            artisan_amount,
            resolver.clone(),
            current_time,
        );

        let token_client = token::Client::new(&env, &token);

        if client_amount > 0 {
            token_client.transfer(
                &env.current_contract_address(),
                &escrow.client,
                &client_amount,
            );
        }

        let mut jury_reward: i128 = 0;

        if artisan_amount > 0 {
            if let Some(cfg) = Self::get_treasury_config(&env) {
                let fee = Self::calculate_fee(artisan_amount, cfg.fee_basis_points);
                let artisan_payout = artisan_amount - fee;

                let reward_bps = Self::get_jury_reward_bps(env.clone());
                jury_reward = Self::calculate_fee(fee, reward_bps);
                let treasury_share = fee - jury_reward;

                if jury_reward > 0 {
                    token_client.transfer(&env.current_contract_address(), &resolver, &jury_reward);
                }

                if treasury_share > 0 {
                    token_client.transfer(
                        &env.current_contract_address(),
                        &cfg.treasury_address,
                        &treasury_share,
                    );
                    events::emit_fee_collected(
                        &env,
                        engagement_id,
                        cfg.treasury_address,
                        escrow.token.clone(),
                        treasury_share,
                    );
                }

                token_client.transfer(
                    &env.current_contract_address(),
                    &escrow.artisan,
                    &artisan_payout,
                );
            } else {
                token_client.transfer(
                    &env.current_contract_address(),
                    &escrow.artisan,
                    &artisan_amount,
                );
            }
        }

        Self::clear_lock(&env);

        jury_reward
    }

    pub fn start_job(env: Env, engagement_id: u64) {
        assert!(!Self::is_paused(&env), "contract is paused");
        let oracle: Address = env
            .storage()
            .persistent()
            .get(&DataKey::Oracle)
            .expect("Oracle not set");
        oracle.require_auth();

        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        if escrow.status != Status::Funded {
            panic!("Escrow must be Funded to transition to InProgress");
        }

        escrow.status = Status::InProgress;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);
    }

    pub fn dispute(env: Env, engagement_id: u64, initiator: Address) {
        assert!(!Self::is_paused(&env), "contract is paused");
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        initiator.require_auth();

        if initiator != escrow.client && initiator != escrow.artisan {
            panic!("Only client or artisan can initiate a dispute");
        }

        if escrow.status != Status::Funded && escrow.status != Status::InProgress {
            panic!("Escrow must be Funded or InProgress to initiate a dispute");
        }

        escrow.status = Status::Disputed;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        let current_time = env.ledger().timestamp();
        // Standardized Event Emission
        events::emit_disputed(
            &env,
            engagement_id,
            escrow.client,
            escrow.artisan,
            escrow.token,
            escrow.material_amount + escrow.labor_amount,
            initiator,
            current_time,
        );
    }

    pub fn resolve_dispute(
        env: Env,
        engagement_id: u64,
        client_amount: i128,
        artisan_amount: i128,
        token: Address,
    ) {
        assert!(!Self::is_paused(&env), "contract is paused");
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        escrow.arbitrator.require_auth();

        if escrow.status != Status::Disputed {
            panic!("Escrow must be in Disputed status to resolve");
        }

        if client_amount < 0 || artisan_amount < 0 {
            panic!("Distribution amounts must be non-negative");
        }

        let remaining = Self::remaining_escrow_balance(&env, engagement_id, &escrow);
        if client_amount + artisan_amount != remaining {
            panic!("Distribution amounts must equal the remaining escrowed amount");
        }

        if token != escrow.token {
            panic!("Token does not match the initialized token for this engagement");
        }

        Self::check_and_set_lock(&env);

        if artisan_amount == 0 {
            escrow.status = Status::Refunded;
        } else if client_amount == 0 {
            escrow.status = Status::Released;
        } else {
            escrow.status = Status::Resolved;
        }

        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        let current_time = env.ledger().timestamp();
        // Standardized Event Emission
        events::emit_resolved(
            &env,
            engagement_id,
            escrow.client.clone(),
            escrow.artisan.clone(),
            escrow.token.clone(),
            client_amount,
            artisan_amount,
            escrow.arbitrator.clone(),
            current_time,
        );

        let token_client = token::Client::new(&env, &token);

        if client_amount > 0 {
            token_client.transfer(
                &env.current_contract_address(),
                &escrow.client,
                &client_amount,
            );
        }

        if artisan_amount > 0 {
            if let Some(cfg) = Self::get_treasury_config(&env) {
                let fee = Self::calculate_fee(artisan_amount, cfg.fee_basis_points);
                let artisan_payout = artisan_amount - fee;

                if fee > 0 {
                    token_client.transfer(
                        &env.current_contract_address(),
                        &cfg.treasury_address,
                        &fee,
                    );
                    events::emit_fee_collected(
                        &env,
                        engagement_id,
                        cfg.treasury_address,
                        escrow.token.clone(),
                        fee,
                    );
                }
                token_client.transfer(
                    &env.current_contract_address(),
                    &escrow.artisan,
                    &artisan_payout,
                );
            } else {
                token_client.transfer(
                    &env.current_contract_address(),
                    &escrow.artisan,
                    &artisan_amount,
                );
            }
        }

        Self::clear_lock(&env);
    }

    pub fn cleanup_expired(env: Env, engagement_ids: Vec<u64>) {
        assert!(!Self::is_paused(&env), "contract is paused");
        for engagement_id in engagement_ids.iter() {
            let key = DataKey::Escrow(engagement_id);
            let escrow: Escrow = match env.storage().persistent().get(&key) {
                Some(e) => e,
                None => continue,
            };

            match escrow.status {
                Status::Released | Status::Refunded | Status::Resolved => {}
                _ => panic!("Escrow {} is not in a finalized state", engagement_id),
            }

            escrow.client.require_auth();

            let current_time = env.ledger().timestamp();
            // Standardized Event Emission
            events::emit_cleaned_up(&env, engagement_id, escrow.client, current_time);

            env.storage().persistent().remove(&key);

            let cfg_key = DataKey::MultiSigConfig(engagement_id);
            if env.storage().persistent().has(&cfg_key) {
                env.storage().persistent().remove(&cfg_key);
            }
            let approvals_key = DataKey::MultiSigApprovals(engagement_id);
            if env.storage().persistent().has(&approvals_key) {
                env.storage().persistent().remove(&approvals_key);
            }
            for aux in [
                DataKey::Milestones(engagement_id),
                DataKey::NextMilestone(engagement_id),
                DataKey::MilestoneReleased(engagement_id),
            ] {
                if env.storage().persistent().has(&aux) {
                    env.storage().persistent().remove(&aux);
                }
            }
        }
    }
}
