#![no_std]

use soroban_sdk::{contract, contractimpl, contracttype, Address, Env};

// ---------------------------------------------------------------------------
// Issue #210 – Reputation Verification via Escrow Hashes
//
// Changes vs. original reputation contract:
//   1. `rate_artisan` now requires an `engagement_id` (escrow reference).
//   2. The contract calls an `EscrowProvider` trait to verify the engagement
//      is in `Released` status before accepting the rating.
//   3. Double-rating the same engagement is prevented via `RatedEngagement`
//      storage keys.
// ---------------------------------------------------------------------------

/// Minimal escrow status we care about.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum EngagementStatus {
    Pending,
    Funded,
    InProgress,
    Released,
    Refunded,
    Disputed,
    Resolved,
}

/// Trait that the reputation contract uses to query escrow state.
/// In production this would be a cross-contract call to the deployed
/// EscrowContract.  In tests we inject a mock.
pub trait EscrowProvider {
    fn get_status(env: &Env, escrow_contract: &Address, engagement_id: u64) -> EngagementStatus;
}

// ---------------------------------------------------------------------------
// Storage keys
// ---------------------------------------------------------------------------
#[contracttype]
#[derive(Clone)]
enum DataKey {
    Reputation(Address),
    /// Marks that engagement `id` has already been used to rate `artisan`.
    RatedEngagement(u64, Address),
}

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq, Default)]
pub struct ReputationData {
    pub total_stars: u64,
    pub review_count: u64,
}

// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------
fn read_reputation(env: &Env, user: &Address) -> ReputationData {
    env.storage()
        .persistent()
        .get(&DataKey::Reputation(user.clone()))
        .unwrap_or_default()
}

fn write_reputation(env: &Env, user: &Address, data: &ReputationData) {
    env.storage()
        .persistent()
        .set(&DataKey::Reputation(user.clone()), data);
}

fn is_engagement_rated(env: &Env, engagement_id: u64, artisan: &Address) -> bool {
    env.storage()
        .persistent()
        .has(&DataKey::RatedEngagement(engagement_id, artisan.clone()))
}

fn mark_engagement_rated(env: &Env, engagement_id: u64, artisan: &Address) {
    env.storage()
        .persistent()
        .set(&DataKey::RatedEngagement(engagement_id, artisan.clone()), &true);
}

// ---------------------------------------------------------------------------
// Contract
// ---------------------------------------------------------------------------
#[contract]
pub struct ReputationContract;

#[contractimpl]
impl ReputationContract {
    /// Rate an artisan.
    ///
    /// * `escrow_contract` – address of the deployed EscrowContract.
    /// * `engagement_id`   – the escrow engagement that backs this review.
    /// * `artisan`         – artisan being rated.
    /// * `stars`           – 1–5.
    ///
    /// Panics if:
    ///   - stars out of range
    ///   - engagement is not in `Released` status
    ///   - engagement has already been used to rate this artisan
    pub fn rate_artisan(
        env: Env,
        escrow_contract: Address,
        engagement_id: u64,
        artisan: Address,
        stars: u64,
    ) {
        if !(1..=5).contains(&stars) {
            panic!("stars not in range");
        }

        // Prevent double-rating the same engagement
        if is_engagement_rated(&env, engagement_id, &artisan) {
            panic!("engagement already rated");
        }

        // Verify the engagement is Released via cross-contract call
        let raw: soroban_sdk::Val = env.invoke_contract(
            &escrow_contract,
            &soroban_sdk::Symbol::new(&env, "get_escrow_status"),
            soroban_sdk::vec![&env, engagement_id.into()],
        );
        // The escrow contract returns a u32 discriminant matching Status enum order:
        // Pending=0, Funded=1, InProgress=2, Released=3, Refunded=4, Disputed=5, Resolved=6
        let status_disc: u32 = soroban_sdk::TryFromVal::try_from_val(&env, &raw)
            .unwrap_or_else(|_| panic!("invalid escrow status response"));
        if status_disc != 3 {
            // 3 == Released
            panic!("engagement not released");
        }

        // Record the rating
        mark_engagement_rated(&env, engagement_id, &artisan);

        let mut data = read_reputation(&env, &artisan);
        data.total_stars += stars;
        data.review_count += 1;
        write_reputation(&env, &artisan, &data);
    }

    pub fn get_reputation(env: Env, user: Address) -> ReputationData {
        read_reputation(&env, &user)
    }

    /// Returns (average_scaled_by_100, review_count)
    pub fn get_stats(env: Env, user: Address) -> (u64, u64) {
        let data = read_reputation(&env, &user);
        if data.review_count == 0 {
            return (0, 0);
        }
        ((data.total_stars * 100) / data.review_count, data.review_count)
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
#[cfg(test)]
mod tests {
    use super::*;
    use soroban_sdk::testutils::Address as _;
    use soroban_sdk::{contract, contractimpl, Env};

    // -----------------------------------------------------------------------
    // Mock escrow contract – returns Released (3) for any engagement_id
    // -----------------------------------------------------------------------
    #[contract]
    pub struct MockEscrowReleased;

    #[contractimpl]
    impl MockEscrowReleased {
        pub fn get_escrow_status(_env: Env, _engagement_id: u64) -> u32 {
            3 // Released
        }
    }

    // -----------------------------------------------------------------------
    // Mock escrow contract – returns Funded (1) for any engagement_id
    // -----------------------------------------------------------------------
    #[contract]
    pub struct MockEscrowFunded;

    #[contractimpl]
    impl MockEscrowFunded {
        pub fn get_escrow_status(_env: Env, _engagement_id: u64) -> u32 {
            1 // Funded – not released
        }
    }

    fn setup_released() -> (Env, Address, Address) {
        let env = Env::default();
        env.mock_all_auths();
        let escrow_id = env.register_contract(None, MockEscrowReleased);
        let rep_id = env.register_contract(None, ReputationContract);
        (env, escrow_id, rep_id)
    }

    #[test]
    fn test_rate_artisan_released_engagement() {
        let (env, escrow_id, rep_id) = setup_released();
        let client = ReputationContractClient::new(&env, &rep_id);
        let artisan = Address::generate(&env);

        client.rate_artisan(&escrow_id, &1u64, &artisan, &5u64);

        let data = client.get_reputation(&artisan);
        assert_eq!(data.total_stars, 5);
        assert_eq!(data.review_count, 1);
    }

    #[test]
    #[should_panic(expected = "engagement already rated")]
    fn test_double_rating_same_engagement_rejected() {
        let (env, escrow_id, rep_id) = setup_released();
        let client = ReputationContractClient::new(&env, &rep_id);
        let artisan = Address::generate(&env);

        client.rate_artisan(&escrow_id, &1u64, &artisan, &5u64);
        // Second call with same engagement_id must panic
        client.rate_artisan(&escrow_id, &1u64, &artisan, &4u64);
    }

    #[test]
    fn test_different_engagements_can_rate_same_artisan() {
        let (env, escrow_id, rep_id) = setup_released();
        let client = ReputationContractClient::new(&env, &rep_id);
        let artisan = Address::generate(&env);

        client.rate_artisan(&escrow_id, &1u64, &artisan, &5u64);
        client.rate_artisan(&escrow_id, &2u64, &artisan, &3u64);

        let (avg, count) = client.get_stats(&artisan);
        assert_eq!(count, 2);
        assert_eq!(avg, 400); // (5+3)/2 * 100
    }

    #[test]
    #[should_panic(expected = "engagement not released")]
    fn test_rate_artisan_non_released_engagement_rejected() {
        let env = Env::default();
        env.mock_all_auths();
        let escrow_id = env.register_contract(None, MockEscrowFunded);
        let rep_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &rep_id);
        let artisan = Address::generate(&env);

        client.rate_artisan(&escrow_id, &1u64, &artisan, &5u64);
    }

    #[test]
    #[should_panic(expected = "stars not in range")]
    fn test_stars_out_of_range_rejected() {
        let (env, escrow_id, rep_id) = setup_released();
        let client = ReputationContractClient::new(&env, &rep_id);
        let artisan = Address::generate(&env);
        client.rate_artisan(&escrow_id, &1u64, &artisan, &6u64);
    }
}
