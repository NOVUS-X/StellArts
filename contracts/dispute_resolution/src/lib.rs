#![no_std]

//! DAO-based dispute resolution jury system for StellArts.
//!
//! Decentralizes dispute resolution: instead of a single administrator or
//! arbitrator deciding the outcome of a disputed escrow, a jury of exactly
//! three highly-rated artisans is selected, votes on the dispute, and the
//! majority verdict is executed against the escrow contract.
//!
//! ## Jury selection
//!
//! [`DisputeResolutionContract::select_jury`] receives a candidate pool from
//! the caller (dispute party or admin). Every candidate is verified on-chain:
//!
//! * rating must be strictly greater than 4.5 (queried from the registered
//!   `reputation` contract; `ema_scaled > 45_000`, i.e. EMA strictly above 4.5 stars),
//! * the artisan must not be a party to the dispute (client or artisan),
//! * no duplicate addresses.
//!
//! Exactly three jurors are then selected uniformly at random from the
//! verified pool using the network-provided [`Env::prng`]. The selected jury
//! is persisted per dispute, and selection cannot be repeated once voting has
//! begun.
//!
//! ## Voting
//!
//! Only the three persisted jurors may vote, and each juror may vote exactly
//! once (votes are immutable). A juror votes for one of three verdicts:
//! `FavorClient` (full refund), `FavorArtisan` (full release), or `Split`
//! (50/50).
//!
//! ## Finalization
//!
//! Once all three jurors have voted, anyone connected to the dispute (juror,
//! party, or admin) may call [`DisputeResolutionContract::finalize`]. The
//! verdict with at least two votes is the majority outcome. A 1-1-1 tie is
//! **not** silently resolved: `finalize` panics, the escrow remains
//! `Disputed`, and the existing arbitrator fallback path stays available.
//!
//! The majority verdict is executed against the escrow contract via
//! `escrow::resolve_dispute_dao`, which pays out the client/artisan shares and
//! transfers the jury reward pool (a configured portion of the protocol fee)
//! back to this contract. `finalize` then distributes that pool to the jurors
//! who voted with the majority — minority/absent jurors receive nothing, and
//! the pool is split exactly (remainder goes to the first majority juror), so
//! the contract can never pay out more than it received.

use soroban_sdk::{
    contract, contractclient, contractimpl, contracttype, token, Address, Env, Symbol, Vec,
};

/// Persistent storage TTL (~60 days) and extension threshold (~1 day),
/// matching the escrow contract's constants.
const DISPUTE_TTL: u32 = 1_036_800;
const TTL_THRESHOLD: u32 = 17_280;

/// Size of the jury.
const JURY_SIZE: u32 = 3;

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Admin,
    EscrowContract,
    ReputationContract,
    /// Dispute record keyed by the disputed escrow's engagement id.
    Dispute(u64),
    /// Immutable vote cast by a juror on a dispute.
    Vote(u64, Address),
    /// Majority verdict once the dispute is finalized.
    Outcome(u64),
}

/// A juror's vote on a dispute.
#[contracttype]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Verdict {
    /// Client receives the full remaining escrow (refund).
    FavorClient,
    /// Artisan receives the full remaining escrow (release).
    FavorArtisan,
    /// Remaining escrow is split 50/50 between client and artisan.
    Split,
}

/// Lifecycle state of a DAO dispute.
#[contracttype]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DisputeStatus {
    /// Registered, jury has not been selected yet.
    AwaitingJury,
    /// Jury selected; votes are being collected.
    Voting,
    /// Majority verdict executed and rewards distributed.
    Resolved,
}

/// A recorded vote, used by read helpers.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Vote {
    pub juror: Address,
    pub verdict: Verdict,
}

/// Full state of a DAO dispute.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Dispute {
    pub engagement_id: u64,
    /// Escrow contract the dispute belongs to (captured at creation).
    pub escrow_contract: Address,
    pub token: Address,
    pub client: Address,
    pub artisan: Address,
    pub status: DisputeStatus,
    /// The exactly-three selected jurors (empty until selected).
    pub jury: Vec<Address>,
    /// Jury reward pool received from the escrow contract on finalization.
    pub reward_amount: i128,
}

#[contracttype]
pub struct DisputeCreatedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
}

#[contracttype]
pub struct JurySelectedEvent {
    pub engagement_id: u64,
    pub jury: Vec<Address>,
}

#[contracttype]
pub struct VoteCastEvent {
    pub engagement_id: u64,
    pub juror: Address,
    pub verdict: Verdict,
}

#[contracttype]
pub struct DisputeFinalizedEvent {
    pub engagement_id: u64,
    pub outcome: Verdict,
    pub client_amount: i128,
    pub artisan_amount: i128,
    pub jury_reward: i128,
}

#[contracttype]
pub struct JuryRewardPaidEvent {
    pub engagement_id: u64,
    pub juror: Address,
    pub amount: i128,
}

/// Mirrors the escrow contract's engagement status layout for cross-contract
/// decoding (variant order must match the escrow contract).
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum EscrowStatus {
    Pending,
    Funded,
    InProgress,
    Released,
    Refunded,
    Disputed,
    Resolved,
}

/// Mirrors the escrow contract's engagement layout for cross-contract decoding.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EscrowEngagement {
    pub client: Address,
    pub artisan: Address,
    pub arbitrator: Address,
    pub token: Address,
    pub material_amount: i128,
    pub labor_amount: i128,
    pub status: EscrowStatus,
    pub deadline: u64,
    pub materials_released: bool,
}

/// Mirrors the reputation contract's aggregated reputation layout.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReputationData {
    pub ema_scaled: u64,
    pub review_count: u64,
}

#[contractclient(name = "EscrowDaoClient")]
pub trait EscrowDao {
    fn get_engagement(env: Env, engagement_id: u64) -> EscrowEngagement;
    fn get_remaining_balance(env: Env, engagement_id: u64) -> i128;
    fn resolve_dispute_dao(
        env: Env,
        engagement_id: u64,
        client_amount: i128,
        artisan_amount: i128,
        token: Address,
    ) -> i128;
}

#[contractclient(name = "ReputationDaoClient")]
pub trait ReputationDao {
    fn get_reputation(env: Env, user: Address) -> ReputationData;
}

#[contract]
pub struct DisputeResolutionContract;

#[contractimpl]
impl DisputeResolutionContract {
    fn read_admin(env: &Env) -> Address {
        env.storage()
            .instance()
            .get(&DataKey::Admin)
            .expect("Admin not set")
    }

    fn read_escrow_contract(env: &Env) -> Address {
        env.storage()
            .persistent()
            .get(&DataKey::EscrowContract)
            .expect("Escrow contract not set")
    }

    fn read_reputation_contract(env: &Env) -> Address {
        env.storage()
            .persistent()
            .get(&DataKey::ReputationContract)
            .expect("Reputation contract not set")
    }

    fn read_dispute(env: &Env, engagement_id: u64) -> Dispute {
        env.storage()
            .persistent()
            .get(&DataKey::Dispute(engagement_id))
            .expect("Dispute not found")
    }

    fn write_dispute(env: &Env, engagement_id: u64, dispute: &Dispute) {
        let key = DataKey::Dispute(engagement_id);
        env.storage().persistent().set(&key, dispute);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, DISPUTE_TTL);
    }

    /// Whether `artisan` is eligible for jury duty for this dispute:
    /// strictly more than 4.5 EMA rating and not a party to the dispute.
    ///
    /// EMA is compared with integer math only:
    /// `average > 4.5`  ⇔  `ema_scaled > 45_000` (scale × 10_000).
    fn is_eligible(env: &Env, artisan: &Address, dispute: &Dispute) -> bool {
        if artisan == &dispute.client || artisan == &dispute.artisan {
            return false;
        }
        let reputation = ReputationDaoClient::new(env, &Self::read_reputation_contract(env))
            .get_reputation(artisan);
        if reputation.review_count == 0 {
            return false;
        }
        reputation.ema_scaled > 45_000
    }

    /// Set the contract admin. Can only be called once.
    pub fn initialize(env: Env, admin: Address) {
        if env.storage().instance().has(&DataKey::Admin) {
            panic!("Admin already set");
        }
        admin.require_auth();
        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage()
            .instance()
            .extend_ttl(TTL_THRESHOLD, DISPUTE_TTL);
    }

    /// Point the contract at the escrow and reputation contracts it operates
    /// with. Admin only.
    pub fn set_contracts(
        env: Env,
        admin: Address,
        escrow_contract: Address,
        reputation_contract: Address,
    ) {
        let stored_admin = Self::read_admin(&env);
        if admin != stored_admin {
            panic!("Only admin can set contracts");
        }
        admin.require_auth();

        let escrow_key = DataKey::EscrowContract;
        env.storage()
            .persistent()
            .set(&escrow_key, &escrow_contract);
        env.storage()
            .persistent()
            .extend_ttl(&escrow_key, TTL_THRESHOLD, DISPUTE_TTL);

        let reputation_key = DataKey::ReputationContract;
        env.storage()
            .persistent()
            .set(&reputation_key, &reputation_contract);
        env.storage()
            .persistent()
            .extend_ttl(&reputation_key, TTL_THRESHOLD, DISPUTE_TTL);
    }

    /// Read the configured escrow and reputation contract addresses.
    pub fn get_contracts(env: Env) -> (Address, Address) {
        (
            Self::read_escrow_contract(&env),
            Self::read_reputation_contract(&env),
        )
    }

    /// Register a DAO dispute for an escrow that is already in `Disputed`
    /// status. Only the client or the artisan of the engagement may register
    /// it, and each engagement can only be registered once.
    pub fn create_dispute(env: Env, caller: Address, engagement_id: u64) {
        caller.require_auth();

        if env
            .storage()
            .persistent()
            .has(&DataKey::Dispute(engagement_id))
        {
            panic!("Dispute already registered for this engagement");
        }

        let escrow_contract = Self::read_escrow_contract(&env);
        let engagement =
            EscrowDaoClient::new(&env, &escrow_contract).get_engagement(&engagement_id);

        if engagement.status != EscrowStatus::Disputed {
            panic!("Escrow is not in Disputed status");
        }
        if caller != engagement.client && caller != engagement.artisan {
            panic!("Only the client or artisan can register a dispute");
        }

        let dispute = Dispute {
            engagement_id,
            escrow_contract,
            token: engagement.token.clone(),
            client: engagement.client.clone(),
            artisan: engagement.artisan.clone(),
            status: DisputeStatus::AwaitingJury,
            jury: Vec::new(&env),
            reward_amount: 0,
        };
        Self::write_dispute(&env, engagement_id, &dispute);

        env.events().publish(
            (Symbol::new(&env, "dispute_created"), engagement_id),
            DisputeCreatedEvent {
                engagement_id,
                client: engagement.client,
                artisan: engagement.artisan,
                token: engagement.token,
            },
        );
    }

    /// Select exactly three random eligible jurors for a dispute.
    ///
    /// `candidates` is the pool provided by the caller; every candidate is
    /// verified on-chain (rating > 4.5 via the reputation contract, not a
    /// dispute party, no duplicates) and the jury is picked uniformly at
    /// random from the verified pool. Only the dispute parties or the admin
    /// may invoke this, and it can only be done once per dispute — the jury is
    /// persisted and cannot be replaced after voting begins.
    pub fn select_jury(env: Env, caller: Address, engagement_id: u64, candidates: Vec<Address>) {
        caller.require_auth();

        let mut dispute = Self::read_dispute(&env, engagement_id);
        if dispute.status != DisputeStatus::AwaitingJury {
            panic!("Jury already selected for this dispute");
        }

        let admin = Self::read_admin(&env);
        if caller != dispute.client && caller != dispute.artisan && caller != admin {
            panic!("Only dispute parties or admin can select the jury");
        }

        // Filter the candidate pool down to verified eligible artisans.
        let mut eligible: Vec<Address> = Vec::new(&env);
        for candidate in candidates.iter() {
            if Self::is_eligible(&env, &candidate, &dispute) {
                let mut duplicate = false;
                for existing in eligible.iter() {
                    if existing == candidate {
                        duplicate = true;
                        break;
                    }
                }
                if !duplicate {
                    eligible.push_back(candidate);
                }
            }
        }

        if eligible.len() < JURY_SIZE {
            panic!("Not enough eligible artisans to form a jury");
        }

        // Uniformly random selection from the verified pool using the
        // network-provided PRNG (Fisher-Yates shuffle, take the first 3).
        env.prng().shuffle(&mut eligible);

        let mut jury: Vec<Address> = Vec::new(&env);
        for i in 0..JURY_SIZE {
            let member = eligible
                .get(i)
                .unwrap_or_else(|| panic!("not enough eligible artisans"));
            jury.push_back(member);
        }

        dispute.jury = jury.clone();
        dispute.status = DisputeStatus::Voting;
        Self::write_dispute(&env, engagement_id, &dispute);

        env.events().publish(
            (Symbol::new(&env, "jury_selected"), engagement_id),
            JurySelectedEvent {
                engagement_id,
                jury,
            },
        );
    }

    /// Cast a vote on a dispute. Only a selected juror may vote, and each
    /// juror votes exactly once — votes cannot be changed or withdrawn.
    pub fn vote(env: Env, juror: Address, engagement_id: u64, verdict: Verdict) {
        juror.require_auth();

        let dispute = Self::read_dispute(&env, engagement_id);
        if dispute.status != DisputeStatus::Voting {
            panic!("Dispute is not accepting votes");
        }

        let mut is_juror = false;
        for selected in dispute.jury.iter() {
            if selected == juror {
                is_juror = true;
                break;
            }
        }
        if !is_juror {
            panic!("Caller is not a juror for this dispute");
        }

        let vote_key = DataKey::Vote(engagement_id, juror.clone());
        if env.storage().persistent().has(&vote_key) {
            panic!("Juror has already voted");
        }
        env.storage().persistent().set(&vote_key, &verdict);
        env.storage()
            .persistent()
            .extend_ttl(&vote_key, TTL_THRESHOLD, DISPUTE_TTL);

        env.events().publish(
            (Symbol::new(&env, "vote_cast"), engagement_id, juror.clone()),
            VoteCastEvent {
                engagement_id,
                juror,
                verdict,
            },
        );
    }

    /// Finalize a dispute once all three jurors have voted.
    ///
    /// The verdict with at least two votes is the majority outcome and is
    /// executed against the escrow contract; the jury reward pool (a
    /// configured portion of the protocol fee) is then distributed to the
    /// jurors who voted with the majority. A 1-1-1 tie is never silently
    /// resolved — `finalize` panics, the dispute stays open, and the escrow
    /// remains `Disputed` so the fallback arbitrator path is preserved.
    ///
    /// Only a juror, a dispute party, or the admin may trigger finalization;
    /// the executed outcome is fully determined by the recorded votes, so no
    /// caller can influence it.
    pub fn finalize(env: Env, caller: Address, engagement_id: u64) {
        caller.require_auth();

        let mut dispute = Self::read_dispute(&env, engagement_id);
        if dispute.status != DisputeStatus::Voting {
            panic!("Dispute is not in voting state");
        }

        let admin = Self::read_admin(&env);
        let mut is_caller_connected = caller == dispute.client || caller == dispute.artisan;
        if !is_caller_connected {
            for selected in dispute.jury.iter() {
                if selected == caller {
                    is_caller_connected = true;
                    break;
                }
            }
        }
        if !is_caller_connected && caller != admin {
            panic!("Only jurors, dispute parties, or admin can finalize");
        }

        // Every juror must have voted.
        let mut votes: Vec<(Address, Verdict)> = Vec::new(&env);
        for selected in dispute.jury.iter() {
            let vote_key = DataKey::Vote(engagement_id, selected.clone());
            let verdict: Verdict = env
                .storage()
                .persistent()
                .get(&vote_key)
                .expect("Not all jurors have voted");
            votes.push_back((selected, verdict));
        }

        // Tally and require a majority (>= 2 of 3 for the same verdict).
        let mut favor_client: u32 = 0;
        let mut favor_artisan: u32 = 0;
        let mut split: u32 = 0;
        for (_, verdict) in votes.iter() {
            match verdict {
                Verdict::FavorClient => favor_client += 1,
                Verdict::FavorArtisan => favor_artisan += 1,
                Verdict::Split => split += 1,
            }
        }

        let outcome = if favor_client >= 2 {
            Verdict::FavorClient
        } else if favor_artisan >= 2 {
            Verdict::FavorArtisan
        } else if split >= 2 {
            Verdict::Split
        } else {
            // 1-1-1 tie: never silently pick a winner.
            panic!("Jury failed to reach a majority");
        };

        // Compute the payout split for the majority verdict.
        let remaining = EscrowDaoClient::new(&env, &dispute.escrow_contract)
            .get_remaining_balance(&engagement_id);
        let (client_amount, artisan_amount) = match outcome {
            Verdict::FavorClient => (remaining, 0),
            Verdict::FavorArtisan => (0, remaining),
            Verdict::Split => {
                let client_share = remaining / 2;
                (client_share, remaining - client_share)
            }
        };

        // Execute the verdict on the escrow contract. The escrow verifies this
        // contract is its registered dispute resolver, transfers the jury
        // reward pool (portion of the protocol fee) to this contract, and
        // returns the exact amount received.
        let jury_reward = EscrowDaoClient::new(&env, &dispute.escrow_contract).resolve_dispute_dao(
            &engagement_id,
            &client_amount,
            &artisan_amount,
            &dispute.token,
        );

        // Distribute the reward pool only to majority jurors. The pool is
        // split exactly (remainder goes to the first majority juror), so this
        // contract can never pay out more than it received.
        if jury_reward > 0 {
            let mut majority_jurors: Vec<Address> = Vec::new(&env);
            for (selected, verdict) in votes.iter() {
                if verdict == outcome {
                    majority_jurors.push_back(selected);
                }
            }

            let count: i128 = majority_jurors.len() as i128;
            let per_juror = jury_reward / count;
            let remainder = jury_reward % count;
            let token_client = token::Client::new(&env, &dispute.token);
            let mut paid: i128 = 0;

            for (i, juror) in majority_jurors.iter().enumerate() {
                let amount = if i == 0 {
                    per_juror + remainder
                } else {
                    per_juror
                };
                if amount > 0 {
                    token_client.transfer(&env.current_contract_address(), &juror, &amount);
                    paid = paid
                        .checked_add(amount)
                        .unwrap_or_else(|| panic!("reward distribution overflow"));
                    env.events().publish(
                        (
                            Symbol::new(&env, "jury_reward_paid"),
                            engagement_id,
                            juror.clone(),
                        ),
                        JuryRewardPaidEvent {
                            engagement_id,
                            juror,
                            amount,
                        },
                    );
                }
            }
            if paid != jury_reward {
                panic!("Reward distribution mismatch");
            }
        }

        let outcome_key = DataKey::Outcome(engagement_id);
        env.storage().persistent().set(&outcome_key, &outcome);
        env.storage()
            .persistent()
            .extend_ttl(&outcome_key, TTL_THRESHOLD, DISPUTE_TTL);

        dispute.reward_amount = jury_reward;
        dispute.status = DisputeStatus::Resolved;
        Self::write_dispute(&env, engagement_id, &dispute);

        env.events().publish(
            (Symbol::new(&env, "dispute_finalized"), engagement_id),
            DisputeFinalizedEvent {
                engagement_id,
                outcome,
                client_amount,
                artisan_amount,
                jury_reward,
            },
        );
    }

    /// Read the majority verdict of a finalized dispute (None if not resolved).
    pub fn get_outcome(env: Env, engagement_id: u64) -> Option<Verdict> {
        env.storage()
            .persistent()
            .get(&DataKey::Outcome(engagement_id))
    }

    /// Read the full dispute record for an engagement (None if not registered).
    pub fn get_dispute(env: Env, engagement_id: u64) -> Option<Dispute> {
        env.storage()
            .persistent()
            .get(&DataKey::Dispute(engagement_id))
    }

    /// Read the selected jury for a dispute (empty until selected).
    pub fn get_jury(env: Env, engagement_id: u64) -> Vec<Address> {
        Self::read_dispute(&env, engagement_id).jury
    }

    /// Read all votes cast on a dispute (empty until the jury votes).
    pub fn get_votes(env: Env, engagement_id: u64) -> Vec<Vote> {
        let dispute = Self::read_dispute(&env, engagement_id);
        let mut votes: Vec<Vote> = Vec::new(&env);
        for selected in dispute.jury.iter() {
            if let Some(verdict) = env
                .storage()
                .persistent()
                .get::<DataKey, Verdict>(&DataKey::Vote(engagement_id, selected.clone()))
            {
                votes.push_back(Vote {
                    juror: selected,
                    verdict,
                });
            }
        }
        votes
    }
}

#[cfg(test)]
mod test;
