#![no_std]

use soroban_sdk::{contract, contractclient, contractimpl, contracttype, Address, Env};

/// Storage key for user reputation data and per-engagement rating flags.
#[contracttype]
#[derive(Clone)]
enum DataKey {
    Reputation(Address),
    EngagementRated(Address, u64),
}

#[contracttype]
pub struct RateArtisanEvent {
    pub artisan: Address,
    pub stars: u64,
    pub timestamp: u64,
}

/// Scale factor for fixed-point EMA arithmetic.
pub const RATING_SCALE: u64 = 10000;
/// Weight applied to the new rating (20%).
pub const NEW_WEIGHT: u64 = 2000;
/// Weight applied to the existing average (80%).
pub const OLD_WEIGHT: u64 = 8000;

/// Public struct containing aggregated review data for a user.
/// Uses an Exponential Moving Average (EMA) stored as a scaled integer
/// to heavily weight recent reviews without storing individual ratings.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq, Default)]
pub struct ReputationData {
    pub average_scaled: u64,
    pub review_count: u64,
}

/// Mirrors the escrow contract status layout for cross-contract decoding.
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

/// Mirrors the escrow contract engagement layout for cross-contract decoding.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EscrowEngagement {
    pub client: Address,
    pub artisan: Address,
    pub arbitrator: Address,
    pub token: Address,
    pub amount: i128,
    pub status: EscrowStatus,
    pub deadline: u64,
}

#[contractclient(name = "EscrowVerifierClient")]
pub trait EscrowVerifier {
    fn get_engagement(env: Env, engagement_id: u64) -> EscrowEngagement;
}

/// Helper function to read reputation data for a user.
/// Returns default values (0 total_stars, 0 review_count) if user has no existing reputation.
pub fn read_reputation(env: &Env, user: &Address) -> ReputationData {
    let key = DataKey::Reputation(user.clone());
    env.storage().persistent().get(&key).unwrap_or_default()
}

/// Helper function to write reputation data for a user.
pub fn write_reputation(env: &Env, user: &Address, data: &ReputationData) {
    let key = DataKey::Reputation(user.clone());
    env.storage().persistent().set(&key, data);
}

fn engagement_rated_key(escrow_contract_id: &Address, engagement_id: u64) -> DataKey {
    DataKey::EngagementRated(escrow_contract_id.clone(), engagement_id)
}

fn has_engagement_been_rated(env: &Env, escrow_contract_id: &Address, engagement_id: u64) -> bool {
    env.storage()
        .persistent()
        .get(&engagement_rated_key(escrow_contract_id, engagement_id))
        .unwrap_or(false)
}

fn mark_engagement_rated(env: &Env, escrow_contract_id: &Address, engagement_id: u64) {
    env.storage().persistent().set(
        &engagement_rated_key(escrow_contract_id, engagement_id),
        &true,
    );
}

#[contract]
pub struct ReputationContract;

#[contractimpl]
impl ReputationContract {
    /// Get reputation data for a user.
    pub fn get_reputation(env: Env, user: Address) -> ReputationData {
        read_reputation(&env, &user)
    }

    /// Set reputation data for a user (for testing/admin purposes).
    pub fn set_reputation(env: Env, user: Address, data: ReputationData) {
        write_reputation(&env, &user, &data);
    }

    /// Update and persist an artisan's reputation score after verifying the completed escrow.
    pub fn rate_artisan(
        env: Env,
        client: Address,
        artisan: Address,
        stars: u64,
        escrow_contract_id: Address,
        engagement_id: u64,
    ) {
        client.require_auth();

        if !(1..=5).contains(&stars) {
            panic!("stars not in range");
        }

        if has_engagement_been_rated(&env, &escrow_contract_id, engagement_id) {
            panic!("engagement already rated");
        }

        let escrow_client = EscrowVerifierClient::new(&env, &escrow_contract_id);
        let engagement = escrow_client.get_engagement(&engagement_id);

        if engagement.client != client {
            panic!("client did not participate in engagement");
        }

        if engagement.artisan != artisan {
            panic!("artisan does not match engagement");
        }

        match engagement.status {
            EscrowStatus::Released | EscrowStatus::Resolved => {}
            _ => panic!("engagement is not completed"),
        }

        let mut artisan_data = Self::get_reputation(env.clone(), artisan.clone());

        if artisan_data.review_count == 0 {
            artisan_data.average_scaled = stars * RATING_SCALE;
        } else {
            let new_rating_scaled = stars * RATING_SCALE;
            artisan_data.average_scaled = (artisan_data.average_scaled * OLD_WEIGHT
                + new_rating_scaled * NEW_WEIGHT)
                / RATING_SCALE;
        }
        artisan_data.review_count += 1;

        Self::set_reputation(env.clone(), artisan.clone(), artisan_data);
        mark_engagement_rated(&env, &escrow_contract_id, engagement_id);

        env.events().publish(
            (),
            RateArtisanEvent {
                artisan,
                stars,
                timestamp: env.ledger().timestamp(),
            },
        );
    }

    /// Get reputation statistics for a user.
    /// Returns (average_scaled_by_10000, count) using the EMA-based score.
    pub fn get_stats(env: Env, user: Address) -> (u64, u64) {
        let data = read_reputation(&env, &user);
        (data.average_scaled, data.review_count)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use escrow::{
        DataKey as EscrowDataKey, Escrow, EscrowContract, Status as EscrowContractStatus,
    };
    use soroban_sdk::testutils::Address as _;
    use soroban_sdk::{Address, Env};

    fn seed_escrow(
        env: &Env,
        escrow_contract_id: &Address,
        engagement_id: u64,
        client: &Address,
        artisan: &Address,
        status: EscrowContractStatus,
    ) {
        let escrow = Escrow {
            client: client.clone(),
            artisan: artisan.clone(),
            arbitrator: Address::generate(env),
            token: Address::generate(env),
            amount: 1_000,
            status,
            deadline: env.ledger().timestamp() + 1_000,
        };

        env.as_contract(escrow_contract_id, || {
            env.storage()
                .persistent()
                .set(&EscrowDataKey::Escrow(engagement_id), &escrow);
        });
    }

    fn setup_contracts(env: &Env) -> (Address, ReputationContractClient<'_>, Address) {
        let reputation_contract_id = env.register_contract(None, ReputationContract);
        let escrow_contract_id = env.register_contract(None, EscrowContract);
        let reputation_client = ReputationContractClient::new(env, &reputation_contract_id);
        (
            reputation_contract_id,
            reputation_client,
            escrow_contract_id,
        )
    }

    #[test]
    fn test_default_reputation_data() {
        let default = ReputationData::default();
        assert_eq!(default.average_scaled, 0);
        assert_eq!(default.review_count, 0);
    }

    #[test]
    fn test_contract_get_reputation_no_data() {
        let env = Env::default();
        let (_, client, _) = setup_contracts(&env);

        let user = Address::generate(&env);
        let reputation = client.get_reputation(&user);

        assert_eq!(reputation.average_scaled, 0);
        assert_eq!(reputation.review_count, 0);
    }

    #[test]
    fn test_contract_set_and_get_reputation() {
        let env = Env::default();
        let (_, client, _) = setup_contracts(&env);

        let user = Address::generate(&env);
        let data = ReputationData {
            average_scaled: 48000,
            review_count: 20,
        };

        client.set_reputation(&user, &data);
        let retrieved = client.get_reputation(&user);

        assert_eq!(retrieved.average_scaled, 48000);
        assert_eq!(retrieved.review_count, 20);
    }

    #[test]
    fn test_multiple_users_independent_reputation() {
        let env = Env::default();
        let (_, client, _) = setup_contracts(&env);

        let user1 = Address::generate(&env);
        let user2 = Address::generate(&env);

        client.set_reputation(
            &user1,
            &ReputationData {
                average_scaled: 48000,
                review_count: 10,
            },
        );
        client.set_reputation(
            &user2,
            &ReputationData {
                average_scaled: 42000,
                review_count: 15,
            },
        );

        let retrieved1 = client.get_reputation(&user1);
        let retrieved2 = client.get_reputation(&user2);

        assert_eq!(retrieved1.average_scaled, 48000);
        assert_eq!(retrieved1.review_count, 10);
        assert_eq!(retrieved2.average_scaled, 42000);
        assert_eq!(retrieved2.review_count, 15);
    }

    #[test]
    fn test_update_existing_reputation() {
        let env = Env::default();
        let (_, client, _) = setup_contracts(&env);

        let user = Address::generate(&env);
        client.set_reputation(
            &user,
            &ReputationData {
                average_scaled: 48000,
                review_count: 5,
            },
        );

        client.set_reputation(
            &user,
            &ReputationData {
                average_scaled: 42000,
                review_count: 12,
            },
        );

        let retrieved = client.get_reputation(&user);
        assert_eq!(retrieved.average_scaled, 42000);
        assert_eq!(retrieved.review_count, 12);
    }

    #[test]
    fn test_rate_artisan_with_verified_completed_engagement() {
        let env = Env::default();
        env.mock_all_auths();
        let (_, client, escrow_contract_id) = setup_contracts(&env);

        let engagement_id = 1;
        let escrow_client = Address::generate(&env);
        let artisan = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            engagement_id,
            &escrow_client,
            &artisan,
            EscrowContractStatus::Released,
        );

        client.rate_artisan(
            &escrow_client,
            &artisan,
            &5,
            &escrow_contract_id,
            &engagement_id,
        );

        let reputation = client.get_reputation(&artisan);
        assert_eq!(reputation.average_scaled, 50000);
        assert_eq!(reputation.review_count, 1);
    }

    #[test]
    #[should_panic]
    fn test_rate_artisan_requires_auth() {
        let env = Env::default();
        let (_, client, escrow_contract_id) = setup_contracts(&env);

        let engagement_id = 1;
        let escrow_client = Address::generate(&env);
        let artisan = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            engagement_id,
            &escrow_client,
            &artisan,
            EscrowContractStatus::Released,
        );

        client.rate_artisan(
            &escrow_client,
            &artisan,
            &5,
            &escrow_contract_id,
            &engagement_id,
        );
    }

    #[test]
    #[should_panic(expected = "client did not participate in engagement")]
    fn test_rate_artisan_rejects_random_user() {
        let env = Env::default();
        env.mock_all_auths();
        let (_, client, escrow_contract_id) = setup_contracts(&env);

        let engagement_id = 1;
        let actual_client = Address::generate(&env);
        let random_user = Address::generate(&env);
        let artisan = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            engagement_id,
            &actual_client,
            &artisan,
            EscrowContractStatus::Released,
        );

        client.rate_artisan(
            &random_user,
            &artisan,
            &5,
            &escrow_contract_id,
            &engagement_id,
        );
    }

    #[test]
    #[should_panic(expected = "engagement is not completed")]
    fn test_rate_artisan_rejects_unfinished_engagement() {
        let env = Env::default();
        env.mock_all_auths();
        let (_, client, escrow_contract_id) = setup_contracts(&env);

        let engagement_id = 1;
        let escrow_client = Address::generate(&env);
        let artisan = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            engagement_id,
            &escrow_client,
            &artisan,
            EscrowContractStatus::Funded,
        );

        client.rate_artisan(
            &escrow_client,
            &artisan,
            &5,
            &escrow_contract_id,
            &engagement_id,
        );
    }

    #[test]
    #[should_panic(expected = "engagement already rated")]
    fn test_rate_artisan_prevents_double_rating() {
        let env = Env::default();
        env.mock_all_auths();
        let (_, client, escrow_contract_id) = setup_contracts(&env);

        let engagement_id = 1;
        let escrow_client = Address::generate(&env);
        let artisan = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            engagement_id,
            &escrow_client,
            &artisan,
            EscrowContractStatus::Released,
        );

        client.rate_artisan(
            &escrow_client,
            &artisan,
            &5,
            &escrow_contract_id,
            &engagement_id,
        );
        client.rate_artisan(
            &escrow_client,
            &artisan,
            &4,
            &escrow_contract_id,
            &engagement_id,
        );
    }

    #[test]
    #[should_panic(expected = "stars not in range")]
    fn test_rate_artisan_not_in_range() {
        let env = Env::default();
        env.mock_all_auths();
        let (_, client, escrow_contract_id) = setup_contracts(&env);

        let engagement_id = 1;
        let escrow_client = Address::generate(&env);
        let artisan = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            engagement_id,
            &escrow_client,
            &artisan,
            EscrowContractStatus::Released,
        );

        client.rate_artisan(
            &escrow_client,
            &artisan,
            &6,
            &escrow_contract_id,
            &engagement_id,
        );
    }

    #[test]
    #[should_panic(expected = "stars not in range")]
    fn test_rate_artisan_not_in_range_zero() {
        let env = Env::default();
        env.mock_all_auths();
        let (_, client, escrow_contract_id) = setup_contracts(&env);

        let engagement_id = 1;
        let escrow_client = Address::generate(&env);
        let artisan = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            engagement_id,
            &escrow_client,
            &artisan,
            EscrowContractStatus::Released,
        );

        client.rate_artisan(
            &escrow_client,
            &artisan,
            &0,
            &escrow_contract_id,
            &engagement_id,
        );
    }

    #[test]
    fn test_get_stats() {
        let env = Env::default();
        let (_, client, _) = setup_contracts(&env);

        let artisan = Address::generate(&env);
        client.set_reputation(
            &artisan,
            &ReputationData {
                average_scaled: 46000,
                review_count: 2,
            },
        );

        let (average_scaled, count) = client.get_stats(&artisan);
        assert_eq!(average_scaled, 46000);
        assert_eq!(count, 2);
    }

    #[test]
    fn test_ema_biases_recent_ratings() {
        let env = Env::default();
        env.mock_all_auths();
        let (_, client, escrow_contract_id) = setup_contracts(&env);

        let artisan = Address::generate(&env);

        // Build up a strong reputation with 10 five-star reviews
        for i in 0..10 {
            let reviewer = Address::generate(&env);
            seed_escrow(
                &env,
                &escrow_contract_id,
                i + 1,
                &reviewer,
                &artisan,
                EscrowContractStatus::Released,
            );
            client.rate_artisan(
                &reviewer,
                &artisan,
                &5,
                &escrow_contract_id,
                &(i as u64 + 1),
            );
        }

        let (avg_before, count_before) = client.get_stats(&artisan);
        assert_eq!(avg_before, 50000);
        assert_eq!(count_before, 10);

        // Add a single 1-star review
        let bad_reviewer = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            11,
            &bad_reviewer,
            &artisan,
            EscrowContractStatus::Released,
        );
        client.rate_artisan(
            &bad_reviewer,
            &artisan,
            &1,
            &escrow_contract_id,
            &11,
        );

        let (avg_after, count_after) = client.get_stats(&artisan);
        assert_eq!(count_after, 11);

        // EMA: (50000 * 8000 + 10000 * 2000) / 10000 = 42000
        assert_eq!(avg_after, 42000);

        // A simple average would give (10*5 + 1) / 11 = 4.636... = 46363
        // EMA gives 42000 = 4.2, which is significantly lower,
        // proving that the weighting algorithm correctly biases new ratings over old ones.
        let simple_average_scaled = (10 * 5 * RATING_SCALE + 1 * RATING_SCALE) / 11;
        assert!(
            avg_after < simple_average_scaled,
            "EMA average {} should be lower than simple average {} after a bad recent review",
            avg_after,
            simple_average_scaled
        );
    }
}

#[cfg(test)]
mod test;
