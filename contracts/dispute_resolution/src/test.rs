//! Unit tests for the DAO-based dispute resolution jury system.
//!
//! Covers: dispute registration, on-chain rating eligibility (strictly > 4.5),
//! exactly-3 unique juror selection, party exclusion, unauthorized callers,
//! one-vote-per-juror enforcement, majority resolution (client/artisan/split),
//! tie handling, jury reward distribution (majority only, exactly-once,
//! overflow-safe), and escrow balance conservation after resolution.

use crate::{DisputeResolutionContract, DisputeResolutionContractClient, DisputeStatus, Verdict};
use soroban_sdk::testutils::Address as AddressTestUtils;
use soroban_sdk::{token, vec, Address, Env, Vec};

struct Ctx {
    env: Env,
    contract_id: Address,
    escrow_id: Address,
    admin: Address,
    token: Address,
    treasury: Address,
    client: DisputeResolutionContractClient<'static>,
    escrow_client: escrow::EscrowContractClient<'static>,
    rep_client: reputation::ReputationContractClient<'static>,
    token_client: token::Client<'static>,
    asset_client: token::StellarAssetClient<'static>,
}

impl Ctx {
    /// Default setup: treasury fee 2.5% (250 bps), 50% of the fee routed to
    /// the jury reward pool (5000 bps).
    fn new() -> Self {
        Self::new_with_config(Some(250), Some(5_000))
    }

    /// Setup with no treasury configured (no fees, no jury rewards).
    fn new_no_treasury() -> Self {
        Self::new_with_config(None, None)
    }

    fn new_with_config(treasury_bps: Option<u32>, jury_bps: Option<u32>) -> Self {
        let env = Env::default();
        env.mock_all_auths_allowing_non_root_auth();

        let admin = Address::generate(&env);
        let treasury = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let tc = env.register_stellar_asset_contract_v2(token_admin);
        let token = tc.address();

        let escrow_id = env.register_contract(None, escrow::EscrowContract);
        let reputation_id = env.register_contract(None, reputation::ReputationContract);
        let contract_id = env.register_contract(None, DisputeResolutionContract);

        let escrow_client = escrow::EscrowContractClient::new(&env, &escrow_id);
        let rep_client = reputation::ReputationContractClient::new(&env, &reputation_id);
        let client = DisputeResolutionContractClient::new(&env, &contract_id);
        let token_client = token::Client::new(&env, &token);
        let asset_client = token::StellarAssetClient::new(&env, &token);

        escrow_client.init_admin(&admin);
        rep_client.set_admin(&admin);
        client.initialize(&admin);
        client.set_contracts(&admin, &escrow_id, &reputation_id);

        // Point the escrow at this contract as its DAO dispute resolver and
        // configure the jury reward share of the protocol fee.
        escrow_client.set_dispute_resolver(&admin, &contract_id);
        if let Some(bps) = jury_bps {
            escrow_client.set_jury_reward_bps(&admin, &bps);
        }
        if let Some(bps) = treasury_bps {
            escrow_client.init_treasury(&admin, &treasury, &bps);
        }

        Ctx {
            env,
            contract_id,
            escrow_id,
            admin,
            token,
            treasury,
            client,
            escrow_client,
            rep_client,
            token_client,
            asset_client,
        }
    }

    /// Seed an artisan's on-chain reputation (EMA scaled × 10_000 / review count).
    fn seed_artisan(&self, artisan: &Address, ema_scaled: u64, review_count: u64) {
        self.rep_client.set_reputation(
            &self.admin,
            artisan,
            &reputation::ReputationData {
                ema_scaled,
                review_count,
            },
        );
    }

    /// Seed a 5.0-star rated artisan.
    fn seed_rated_artisan(&self) -> Address {
        let artisan = Address::generate(&self.env);
        self.seed_artisan(&artisan, 50_000, 1);
        artisan
    }

    /// Create a funded escrow and dispute it. Returns the engagement id.
    fn fund_and_dispute(&self, client: &Address, artisan: &Address, amount: i128) -> u64 {
        let arbitrator = Address::generate(&self.env);
        let deadline = self.env.ledger().timestamp() + 86_400;
        let id = self.escrow_client.initialize(
            client,
            artisan,
            &arbitrator,
            &self.token,
            &amount,
            &0i128,
            &deadline,
            &vec![&self.env],
            &0u32,
            &vec![&self.env],
        );
        self.asset_client.mint(client, &amount);
        self.escrow_client.deposit(&id, &self.token);
        self.escrow_client.dispute(&id, client);
        id
    }

    /// Full setup for a dispute with a default 5.0-rated artisan party:
    /// returns (engagement_id, client, artisan).
    fn setup_dispute(&self, amount: i128) -> (u64, Address, Address) {
        let client = Address::generate(&self.env);
        let artisan = self.seed_rated_artisan();
        let id = self.fund_and_dispute(&client, &artisan, amount);
        self.client.create_dispute(&client, &id);
        (id, client, artisan)
    }

    /// Select a jury for `id` from `candidates` as `caller`.
    fn select_jury(&self, id: u64, candidates: &Vec<Address>, caller: &Address) {
        self.client.select_jury(caller, &id, candidates);
    }

    /// Select a jury from three freshly seeded 5.0-rated artisans.
    /// Returns the three candidate artisans.
    fn setup_jury(&self, id: u64, caller: &Address) -> Vec<Address> {
        let a = self.seed_rated_artisan();
        let b = self.seed_rated_artisan();
        let c = self.seed_rated_artisan();
        let candidates = vec![&self.env, a.clone(), b.clone(), c.clone()];
        self.select_jury(id, &candidates, caller);
        vec![&self.env, a, b, c]
    }

    /// Cast a vote from each (juror, verdict) pair.
    fn cast_votes(&self, id: &u64, votes: &[(Address, Verdict)]) {
        for (juror, verdict) in votes {
            self.client.vote(juror, id, verdict);
        }
    }

    /// Get the escrow status as stored in the escrow contract.
    fn escrow_status(&self, id: u64) -> escrow::Status {
        self.env.as_contract(&self.escrow_id, || {
            self.env
                .storage()
                .persistent()
                .get::<escrow::DataKey, escrow::Escrow>(&escrow::DataKey::Escrow(id))
                .expect("Escrow should exist")
                .status
        })
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Dispute creation / registration
// ─────────────────────────────────────────────────────────────────────────────

/// D-1: A disputed escrow can be registered as a DAO dispute by the client.
#[test]
fn test_create_dispute_registers_dispute() {
    let ctx = Ctx::new();
    let client = Address::generate(&ctx.env);
    let artisan = ctx.seed_rated_artisan();
    let id = ctx.fund_and_dispute(&client, &artisan, 1_000);

    ctx.client.create_dispute(&client, &id);

    let dispute = ctx.client.get_dispute(&id).expect("dispute should exist");
    assert_eq!(dispute.engagement_id, id);
    assert_eq!(dispute.escrow_contract, ctx.escrow_id);
    assert_eq!(dispute.token, ctx.token);
    assert_eq!(dispute.client, client);
    assert_eq!(dispute.artisan, artisan);
    assert_eq!(dispute.status, DisputeStatus::AwaitingJury);
    assert_eq!(dispute.jury.len(), 0);
    assert_eq!(ctx.client.get_outcome(&id), None);
}

/// D-2: The artisan may also register the dispute.
#[test]
fn test_create_dispute_by_artisan() {
    let ctx = Ctx::new();
    let client = Address::generate(&ctx.env);
    let artisan = ctx.seed_rated_artisan();
    let id = ctx.fund_and_dispute(&client, &artisan, 1_000);

    ctx.client.create_dispute(&artisan, &id);

    assert!(ctx.client.get_dispute(&id).is_some());
}

/// D-3: A dispute can only be registered for an escrow in Disputed status.
#[test]
#[should_panic(expected = "Escrow is not in Disputed status")]
fn test_create_dispute_requires_disputed_escrow() {
    let ctx = Ctx::new();
    let client = Address::generate(&ctx.env);
    let artisan = ctx.seed_rated_artisan();
    let arbitrator = Address::generate(&ctx.env);
    let deadline = ctx.env.ledger().timestamp() + 86_400;
    // Fund the escrow but never dispute it — it stays in Funded status.
    let id = ctx.escrow_client.initialize(
        &client,
        &artisan,
        &arbitrator,
        &ctx.token,
        &1_000i128,
        &0i128,
        &deadline,
        &vec![&ctx.env],
        &0u32,
        &vec![&ctx.env],
    );
    ctx.asset_client.mint(&client, &1_000i128);
    ctx.escrow_client.deposit(&id, &ctx.token);
    assert_eq!(ctx.escrow_status(id), escrow::Status::Funded);

    // Registration on a non-disputed escrow must fail.
    ctx.client.create_dispute(&client, &id);
}

/// D-4: A third party cannot register a dispute.
#[test]
#[should_panic(expected = "Only the client or artisan can register a dispute")]
fn test_create_dispute_unauthorized_caller_fails() {
    let ctx = Ctx::new();
    let client = Address::generate(&ctx.env);
    let artisan = ctx.seed_rated_artisan();
    let id = ctx.fund_and_dispute(&client, &artisan, 1_000);

    let stranger = Address::generate(&ctx.env);
    ctx.client.create_dispute(&stranger, &id);
}

/// D-5: An engagement can only be registered once.
#[test]
#[should_panic(expected = "Dispute already registered for this engagement")]
fn test_create_dispute_duplicate_registration_fails() {
    let ctx = Ctx::new();
    let client = Address::generate(&ctx.env);
    let artisan = ctx.seed_rated_artisan();
    let id = ctx.fund_and_dispute(&client, &artisan, 1_000);

    ctx.client.create_dispute(&client, &id);
    ctx.client.create_dispute(&client, &id);
}

/// D-6: Unknown engagement ids are rejected.
#[test]
#[should_panic(expected = "Escrow not found")]
fn test_create_dispute_nonexistent_escrow_fails() {
    let ctx = Ctx::new();
    let client = Address::generate(&ctx.env);
    ctx.client.create_dispute(&client, &999);
}

// ─────────────────────────────────────────────────────────────────────────────
// Jury selection
// ─────────────────────────────────────────────────────────────────────────────

/// J-1: Exactly three unique jurors are selected from an eligible pool.
#[test]
fn test_select_jury_selects_exactly_three_unique_jurors() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    let d = ctx.seed_rated_artisan();
    let e = ctx.seed_rated_artisan();
    let candidates = vec![&ctx.env, a, b, c, d, e];
    ctx.select_jury(id, &candidates, &client);

    let jury = ctx.client.get_jury(&id);
    assert_eq!(jury.len(), 3, "jury must have exactly 3 members");

    // All jurors must be unique and drawn from the eligible pool.
    for i in 0..jury.len() {
        for j in (i + 1)..jury.len() {
            assert_ne!(jury.get(i).unwrap(), jury.get(j).unwrap());
        }
        let mut in_pool = false;
        for cand in candidates.iter() {
            if cand == jury.get(i).unwrap() {
                in_pool = true;
            }
        }
        assert!(in_pool, "juror must come from the eligible pool");
    }

    let dispute = ctx.client.get_dispute(&id).unwrap();
    assert_eq!(dispute.status, DisputeStatus::Voting);
}

/// J-2: An artisan with a rating of exactly 4.5 is not eligible.
#[test]
fn test_rating_exactly_4_5_rejected() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);

    let exactly_4_5 = Address::generate(&ctx.env);
    ctx.seed_artisan(&exactly_4_5, 45_000, 2); // exactly 4.5 EMA

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    let candidates = vec![&ctx.env, exactly_4_5.clone(), a, b, c];
    ctx.select_jury(id, &candidates, &client);

    let jury = ctx.client.get_jury(&id);
    assert_eq!(jury.len(), 3);
    for juror in jury.iter() {
        assert_ne!(juror, exactly_4_5, "4.5-rated artisan must be rejected");
    }
}

/// J-3: An artisan with a rating below 4.5 is not eligible.
#[test]
fn test_rating_below_4_5_rejected() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);

    let below = Address::generate(&ctx.env);
    ctx.seed_artisan(&below, 40_000, 1); // 4.0 EMA
    let unrated = Address::generate(&ctx.env); // no reviews at all

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    let candidates = vec![&ctx.env, below.clone(), unrated.clone(), a, b, c];
    ctx.select_jury(id, &candidates, &client);

    let jury = ctx.client.get_jury(&id);
    assert_eq!(jury.len(), 3);
    for juror in jury.iter() {
        assert_ne!(juror, below, "below-4.5 artisan must be rejected");
        assert_ne!(juror, unrated, "unrated artisan must be rejected");
    }
}

/// J-4: An artisan with a rating above 4.5 is eligible (4.666… qualifies).
#[test]
fn test_rating_above_4_5_eligible() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);

    let above = Address::generate(&ctx.env);
    ctx.seed_artisan(&above, 47_000, 3); // above 4.5 EMA

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let candidates = vec![&ctx.env, above.clone(), a, b];
    ctx.select_jury(id, &candidates, &client);

    let jury = ctx.client.get_jury(&id);
    assert_eq!(jury.len(), 3);
    let mut found = false;
    for juror in jury.iter() {
        if juror == above {
            found = true;
        }
    }
    assert!(found, "above-4.5 artisan should be eligible");
}

/// J-5: The dispute parties (client and artisan) can never be jurors.
#[test]
fn test_dispute_parties_cannot_be_jurors() {
    let ctx = Ctx::new();
    let (id, client, artisan) = ctx.setup_dispute(1_000);

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    let candidates = vec![&ctx.env, client.clone(), artisan.clone(), a, b, c];
    ctx.select_jury(id, &candidates, &client);

    let jury = ctx.client.get_jury(&id);
    assert_eq!(jury.len(), 3);
    for juror in jury.iter() {
        assert_ne!(juror, client, "client cannot serve as juror");
        assert_ne!(juror, artisan, "dispute artisan cannot serve as juror");
    }
}

/// J-6: Only the dispute parties or the admin may select the jury.
#[test]
#[should_panic(expected = "Only dispute parties or admin can select the jury")]
fn test_select_jury_unauthorized_caller_fails() {
    let ctx = Ctx::new();
    let (id, _client, _) = ctx.setup_dispute(1_000);

    let stranger = Address::generate(&ctx.env);
    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    ctx.select_jury(id, &vec![&ctx.env, a, b, c], &stranger);
}

/// J-7: The admin may select the jury.
#[test]
fn test_select_jury_allows_admin() {
    let ctx = Ctx::new();
    let (id, _, _) = ctx.setup_dispute(1_000);

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    ctx.select_jury(id, &vec![&ctx.env, a, b, c], &ctx.admin);

    assert_eq!(ctx.client.get_jury(&id).len(), 3);
}

/// J-8: Selection requires a registered dispute.
#[test]
#[should_panic(expected = "Dispute not found")]
fn test_select_jury_requires_registered_dispute() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);
    // Register a second dispute-free engagement id (1) — here we use an id
    // that was never registered as a DAO dispute.
    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    // id+1 exists as an escrow but has no DAO dispute record.
    ctx.select_jury(id + 1, &vec![&ctx.env, a, b, c], &client);
}

/// J-9: Fewer than three eligible candidates cannot form a jury.
#[test]
#[should_panic(expected = "Not enough eligible artisans to form a jury")]
fn test_select_jury_not_enough_eligible_fails() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let low = Address::generate(&ctx.env);
    ctx.seed_artisan(&low, 40_000, 1);
    ctx.select_jury(id, &vec![&ctx.env, a, b, low], &client);
}

/// J-10: The jury cannot be re-selected once chosen (persisted, immutable).
#[test]
#[should_panic(expected = "Jury already selected for this dispute")]
fn test_select_jury_cannot_be_repeated() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    ctx.select_jury(id, &vec![&ctx.env, a, b, c], &client);
    // Second selection attempt must be rejected.
    let d = ctx.seed_rated_artisan();
    let e = ctx.seed_rated_artisan();
    let f = ctx.seed_rated_artisan();
    ctx.select_jury(id, &vec![&ctx.env, d, e, f], &client);
}

/// J-11: Duplicate candidates in the pool are deduplicated, not juror-able.
#[test]
fn test_select_jury_deduplicates_candidates() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);

    let a = ctx.seed_rated_artisan();
    let b = ctx.seed_rated_artisan();
    let c = ctx.seed_rated_artisan();
    // a appears twice and b appears twice; pool has 3 unique eligible.
    let candidates = vec![
        &ctx.env,
        a.clone(),
        a.clone(),
        b.clone(),
        b.clone(),
        c.clone(),
    ];
    ctx.select_jury(id, &candidates, &client);

    let jury = ctx.client.get_jury(&id);
    assert_eq!(jury.len(), 3, "duplicates must not inflate the jury");
    let mut seen_a = 0;
    for juror in jury.iter() {
        if juror == a {
            seen_a += 1;
        }
    }
    assert_eq!(seen_a, 1, "each juror appears at most once");
}

// ─────────────────────────────────────────────────────────────────────────────
// Voting
// ─────────────────────────────────────────────────────────────────────────────

/// V-1: A selected juror can cast a vote.
#[test]
fn test_juror_vote_succeeds() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);
    let jurors = ctx.setup_jury(id, &client);

    ctx.client
        .vote(&jurors.get(0).unwrap(), &id, &Verdict::FavorClient);

    let votes = ctx.client.get_votes(&id);
    assert_eq!(votes.len(), 1);
    assert_eq!(votes.get(0).unwrap().juror, jurors.get(0).unwrap());
    assert_eq!(votes.get(0).unwrap().verdict, Verdict::FavorClient);
}

/// V-2: A non-juror cannot vote.
#[test]
#[should_panic(expected = "Caller is not a juror for this dispute")]
fn test_non_juror_vote_fails() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);
    let _jurors = ctx.setup_jury(id, &client);

    let stranger = Address::generate(&ctx.env);
    ctx.client.vote(&stranger, &id, &Verdict::FavorClient);
}

/// V-3: A juror can only vote once.
#[test]
#[should_panic(expected = "Juror has already voted")]
fn test_duplicate_vote_fails() {
    let ctx = Ctx::new();
    let (id, client, _) = ctx.setup_dispute(1_000);
    let jurors = ctx.setup_jury(id, &client);

    let juror = jurors.get(0).unwrap();
    ctx.client.vote(&juror, &id, &Verdict::FavorClient);
    ctx.client.vote(&juror, &id, &Verdict::FavorArtisan);
}

/// V-4: Voting before a jury is selected is rejected.
#[test]
#[should_panic(expected = "Dispute is not accepting votes")]
fn test_vote_before_jury_selected_fails() {
    let ctx = Ctx::new();
    let (id, _client, _) = ctx.setup_dispute(1_000);
    // No jury selected yet — voting must fail even for a rated artisan.
    let artisan = ctx.seed_rated_artisan();
    ctx.client.vote(&artisan, &id, &Verdict::FavorClient);
}

/// V-5: Voting on an unregistered dispute is rejected.
#[test]
#[should_panic(expected = "Dispute not found")]
fn test_vote_unregistered_dispute_fails() {
    let ctx = Ctx::new();
    let artisan = ctx.seed_rated_artisan();
    ctx.client.vote(&artisan, &42, &Verdict::FavorClient);
}

// ─────────────────────────────────────────────────────────────────────────────
// Finalization & majority resolution
// ─────────────────────────────────────────────────────────────────────────────

/// F-1: 2-of-3 FavorClient → full refund to the client; escrow Refunded.
#[test]
fn test_finalize_majority_favor_client() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, _) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorClient),
            (jurors.get(1).unwrap(), Verdict::FavorClient),
            (jurors.get(2).unwrap(), Verdict::FavorArtisan),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    // Escrow state + dispute state.
    assert_eq!(ctx.escrow_status(id), escrow::Status::Refunded);
    let dispute = ctx.client.get_dispute(&id).unwrap();
    assert_eq!(dispute.status, DisputeStatus::Resolved);
    assert_eq!(ctx.client.get_outcome(&id), Some(Verdict::FavorClient));
    assert_eq!(dispute.reward_amount, 0);

    // Balances: client gets everything back, no fee (client refunds are fee-free).
    assert_eq!(ctx.token_client.balance(&client_addr), amount);
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
    assert_eq!(ctx.token_client.balance(&ctx.escrow_id), 0);
    assert_eq!(ctx.token_client.balance(&ctx.treasury), 0);
}

/// F-2: 2-of-3 FavorArtisan → full release; escrow Released; fee split.
#[test]
fn test_finalize_majority_favor_artisan() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, artisan_addr) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorArtisan),
            (jurors.get(1).unwrap(), Verdict::FavorArtisan),
            (jurors.get(2).unwrap(), Verdict::FavorClient),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    assert_eq!(ctx.escrow_status(id), escrow::Status::Released);
    let dispute = ctx.client.get_dispute(&id).unwrap();
    assert_eq!(dispute.status, DisputeStatus::Resolved);
    assert_eq!(ctx.client.get_outcome(&id), Some(Verdict::FavorArtisan));

    // 2.5% fee on 10,000 = 250; 50% of the fee (125) funds the jury pool,
    // 125 goes to the treasury; artisan receives 9,750.
    assert_eq!(ctx.token_client.balance(&artisan_addr), 9_750);
    assert_eq!(ctx.token_client.balance(&ctx.treasury), 125);
    assert_eq!(ctx.token_client.balance(&ctx.escrow_id), 0);
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
    assert_eq!(ctx.token_client.balance(&client_addr), 0);
}

/// F-3: 2-of-3 Split → 50/50 distribution; escrow Resolved.
#[test]
fn test_finalize_majority_split() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, artisan_addr) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::Split),
            (jurors.get(1).unwrap(), Verdict::Split),
            (jurors.get(2).unwrap(), Verdict::FavorClient),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    assert_eq!(ctx.escrow_status(id), escrow::Status::Resolved);
    assert_eq!(ctx.client.get_outcome(&id), Some(Verdict::Split));

    // Split: 5,000 each. Fee on artisan share (5,000) = 125; jury pool 62,
    // treasury 63; artisan receives 4,875, client 5,000.
    assert_eq!(ctx.token_client.balance(&client_addr), 5_000);
    assert_eq!(ctx.token_client.balance(&artisan_addr), 4_875);
    assert_eq!(ctx.token_client.balance(&ctx.treasury), 63);
    assert_eq!(ctx.token_client.balance(&ctx.escrow_id), 0);
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
}

/// F-4: An odd remaining balance is split without rounding loss (no dust).
#[test]
fn test_finalize_split_odd_remaining() {
    let ctx = Ctx::new();
    let amount: i128 = 10_001;
    let (id, client_addr, artisan_addr) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::Split),
            (jurors.get(1).unwrap(), Verdict::Split),
            (jurors.get(2).unwrap(), Verdict::FavorArtisan),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    assert_eq!(ctx.escrow_status(id), escrow::Status::Resolved);
    // client 5,000 (floor), artisan 5,001 (remainder) — sums to 10,001.
    assert_eq!(ctx.token_client.balance(&client_addr), 5_000);
    assert_eq!(ctx.token_client.balance(&artisan_addr), 5_001 - 125);
    assert_eq!(ctx.token_client.balance(&ctx.treasury), 125 - 62);
    assert_eq!(ctx.token_client.balance(&ctx.escrow_id), 0);
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
}

/// F-5: A 1-1-1 tie is never silently resolved — finalize panics.
#[test]
#[should_panic(expected = "Jury failed to reach a majority")]
fn test_finalize_tie_fails() {
    let ctx = Ctx::new();
    let (id, client_addr, _) = ctx.setup_dispute(1_000);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorClient),
            (jurors.get(1).unwrap(), Verdict::FavorArtisan),
            (jurors.get(2).unwrap(), Verdict::Split),
        ],
    );

    // The panic happens before any state change: no payout is executed and no
    // winner is selected; the escrow remains Disputed (arbitrator fallback).
    ctx.client.finalize(&client_addr, &id);
}

/// F-6: Finalization requires all three jurors to have voted.
#[test]
#[should_panic(expected = "Not all jurors have voted")]
fn test_finalize_not_all_voted_fails() {
    let ctx = Ctx::new();
    let (id, client_addr, _) = ctx.setup_dispute(1_000);
    let jurors = ctx.setup_jury(id, &client_addr);

    // Only two jurors vote (both FavorClient) — the third has not voted.
    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorClient),
            (jurors.get(1).unwrap(), Verdict::FavorClient),
        ],
    );
    ctx.client.finalize(&client_addr, &id);
}

/// F-7: Unauthorized callers cannot trigger finalization.
#[test]
#[should_panic]
fn test_finalize_unauthorized_caller_fails() {
    let ctx = Ctx::new();
    let (id, client_addr, _) = ctx.setup_dispute(1_000);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorClient),
            (jurors.get(1).unwrap(), Verdict::FavorClient),
            (jurors.get(2).unwrap(), Verdict::FavorClient),
        ],
    );

    // Clear mock auths: a stranger must not be able to finalize.
    ctx.env.set_auths(&[]);
    let stranger = Address::generate(&ctx.env);
    ctx.client.finalize(&stranger, &id);
}

/// F-8: A juror may trigger finalization (authorized caller).
#[test]
fn test_finalize_allows_juror_caller() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, _) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorArtisan),
            (jurors.get(1).unwrap(), Verdict::FavorArtisan),
            (jurors.get(2).unwrap(), Verdict::FavorArtisan),
        ],
    );

    // A juror (not a party) finalizes.
    ctx.client.finalize(&jurors.get(0).unwrap(), &id);

    assert_eq!(ctx.escrow_status(id), escrow::Status::Released);
    assert_eq!(
        ctx.client.get_dispute(&id).unwrap().status,
        DisputeStatus::Resolved
    );
}

/// F-9: An already-resolved dispute cannot be resolved again.
#[test]
#[should_panic(expected = "Dispute is not in voting state")]
fn test_finalize_after_resolved_fails() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, _) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorClient),
            (jurors.get(1).unwrap(), Verdict::FavorClient),
            (jurors.get(2).unwrap(), Verdict::FavorClient),
        ],
    );

    ctx.client.finalize(&client_addr, &id);
    // Second finalize must be rejected — rewards can never be paid twice.
    ctx.client.finalize(&client_addr, &id);
}

/// F-10: Finalization before a jury is selected is rejected.
#[test]
#[should_panic(expected = "Dispute is not in voting state")]
fn test_finalize_before_jury_selected_fails() {
    let ctx = Ctx::new();
    let (id, client_addr, _) = ctx.setup_dispute(1_000);
    ctx.client.finalize(&client_addr, &id);
}

// ─────────────────────────────────────────────────────────────────────────────
// Jury rewards
// ─────────────────────────────────────────────────────────────────────────────

/// R-1: Majority jurors receive the jury reward pool; minority jurors receive
/// nothing. The pool is split exactly (remainder to the first majority juror)
/// and the contract holds no dust afterwards.
#[test]
fn test_majority_jurors_receive_reward_minority_none() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, _) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    let (j1, j2, j3) = (
        jurors.get(0).unwrap(),
        jurors.get(1).unwrap(),
        jurors.get(2).unwrap(),
    );
    ctx.cast_votes(
        &id,
        &[
            (j1.clone(), Verdict::FavorArtisan),
            (j2.clone(), Verdict::FavorArtisan),
            (j3.clone(), Verdict::FavorClient),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    // fee = 250, jury pool = 125 → 63 to first majority juror, 62 to second.
    assert_eq!(ctx.token_client.balance(&j1), 63);
    assert_eq!(ctx.token_client.balance(&j2), 62);
    assert_eq!(
        ctx.token_client.balance(&j3),
        0,
        "minority juror gets nothing"
    );
    // The contract must not retain any of the reward pool.
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
}

/// R-2: Rewards are paid exactly once (the reward pool is fully drained on the
/// single finalize; a second finalize is rejected — see F-9).
#[test]
fn test_rewards_distributed_exactly_once() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, _) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    // Unanimous verdict → all three jurors are majority jurors.
    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorArtisan),
            (jurors.get(1).unwrap(), Verdict::FavorArtisan),
            (jurors.get(2).unwrap(), Verdict::FavorArtisan),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    // fee = 250, jury pool = 125 split 3 ways: 43 + 41 + 41 = 125.
    let b1 = ctx.token_client.balance(&jurors.get(0).unwrap());
    let b2 = ctx.token_client.balance(&jurors.get(1).unwrap());
    let b3 = ctx.token_client.balance(&jurors.get(2).unwrap());
    assert_eq!(b1 + b2 + b3, 125);
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
}

/// R-3: When no treasury is configured there is no fee, hence no jury reward —
/// the artisan receives the full amount and nobody is paid extra.
#[test]
fn test_no_reward_without_treasury() {
    let ctx = Ctx::new_no_treasury();
    let amount: i128 = 10_000;
    let (id, client_addr, artisan_addr) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorArtisan),
            (jurors.get(1).unwrap(), Verdict::FavorArtisan),
            (jurors.get(2).unwrap(), Verdict::FavorArtisan),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    assert_eq!(ctx.escrow_status(id), escrow::Status::Released);
    assert_eq!(ctx.token_client.balance(&artisan_addr), amount);
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
    for i in 0..3 {
        assert_eq!(ctx.token_client.balance(&jurors.get(i).unwrap()), 0);
    }
    let dispute = ctx.client.get_dispute(&id).unwrap();
    assert_eq!(dispute.reward_amount, 0);
}

/// R-4: A full-refund verdict generates no fee, so no rewards are paid.
#[test]
fn test_favor_client_pays_no_rewards() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, artisan_addr) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorClient),
            (jurors.get(1).unwrap(), Verdict::FavorClient),
            (jurors.get(2).unwrap(), Verdict::FavorClient),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    assert_eq!(ctx.token_client.balance(&client_addr), amount);
    assert_eq!(ctx.token_client.balance(&artisan_addr), 0);
    assert_eq!(ctx.token_client.balance(&ctx.treasury), 0);
    for i in 0..3 {
        assert_eq!(ctx.token_client.balance(&jurors.get(i).unwrap()), 0);
    }
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
    assert_eq!(ctx.token_client.balance(&ctx.escrow_id), 0);
}

/// R-5: Escrow balances remain correct after resolution — full conservation.
#[test]
fn test_escrow_balances_conserved_after_resolution() {
    let ctx = Ctx::new();
    let amount: i128 = 10_000;
    let (id, client_addr, artisan_addr) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorArtisan),
            (jurors.get(1).unwrap(), Verdict::FavorArtisan),
            (jurors.get(2).unwrap(), Verdict::Split),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    // Every unit of the original escrow must be accounted for.
    let mut total: i128 = 0;
    total += ctx.token_client.balance(&client_addr);
    total += ctx.token_client.balance(&artisan_addr);
    total += ctx.token_client.balance(&ctx.treasury);
    total += ctx.token_client.balance(&ctx.escrow_id);
    total += ctx.token_client.balance(&ctx.contract_id);
    for i in 0..3 {
        total += ctx.token_client.balance(&jurors.get(i).unwrap());
    }
    assert_eq!(total, amount, "tokens must be conserved");
}

/// R-6: Large escrow amounts resolve without overflow and stay conserved.
#[test]
fn test_large_amounts_no_overflow() {
    let ctx = Ctx::new();
    let amount: i128 = 1_000_000_000_000_000_000; // 10^18
    let (id, client_addr, artisan_addr) = ctx.setup_dispute(amount);
    let jurors = ctx.setup_jury(id, &client_addr);

    ctx.cast_votes(
        &id,
        &[
            (jurors.get(0).unwrap(), Verdict::FavorArtisan),
            (jurors.get(1).unwrap(), Verdict::FavorArtisan),
            (jurors.get(2).unwrap(), Verdict::FavorArtisan),
        ],
    );

    ctx.client.finalize(&client_addr, &id);

    let fee = amount * 250 / 10_000;
    let jury_pool = fee * 5_000 / 10_000;
    let treasury_share = fee - jury_pool;
    assert_eq!(
        ctx.token_client.balance(&artisan_addr),
        amount - fee,
        "artisan receives payout minus fee"
    );
    assert_eq!(ctx.token_client.balance(&ctx.treasury), treasury_share);
    assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
    assert_eq!(ctx.token_client.balance(&ctx.escrow_id), 0);

    let mut juror_total: i128 = 0;
    for i in 0..3 {
        juror_total += ctx.token_client.balance(&jurors.get(i).unwrap());
    }
    assert_eq!(juror_total, jury_pool);
}
