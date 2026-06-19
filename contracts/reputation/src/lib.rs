#![no_std]

use soroban_sdk::{contract, contractclient, contractimpl, contracttype, Address, Env};

/// Storage key for user reputation data and per-engagement rating flags.
#[contracttype]
#[derive(Clone)]
enum DataKey {
    Reputation(Address),
    EngagementRated(Address, u64),
    HasRated(Address, Address),
    Admin,
}

#[contracttype]
pub struct RateArtisanEvent {
    pub artisan: Address,
    pub stars: u64,
    pub timestamp: u64,
}

/// Public struct containing aggregated review data for a user.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq, Default)]
pub struct ReputationData {
    pub total_stars: u64,
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
    pub material_amount: i128,
    pub labor_amount: i128,
    pub status: EscrowStatus,
    pub deadline: u64,
    pub materials_released: bool,
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

fn has_rated_key(caller: &Address, artisan: &Address) -> DataKey {
    DataKey::HasRated(caller.clone(), artisan.clone())
}

fn has_caller_rated_artisan(env: &Env, caller: &Address, artisan: &Address) -> bool {
    env.storage()
        .persistent()
        .get(&has_rated_key(caller, artisan))
        .unwrap_or(false)
}

fn mark_caller_rated_artisan(env: &Env, caller: &Address, artisan: &Address) {
    env.storage()
        .persistent()
        .set(&has_rated_key(caller, artisan), &true);
}

fn read_admin(env: &Env) -> Address {
    env.storage()
        .persistent()
        .get(&DataKey::Admin)
        .expect("Admin not set")
}

#[contract]
pub struct ReputationContract;

#[contractimpl]
impl ReputationContract {
    /// Get reputation data for a user.
    pub fn get_reputation(env: Env, user: Address) -> ReputationData {
        read_reputation(&env, &user)
    }

    /// Store the contract admin address.
    pub fn set_admin(env: Env, admin: Address) {
        admin.require_auth();
        env.storage().persistent().set(&DataKey::Admin, &admin);
    }

    /// Set reputation data for a user (admin only).
    pub fn set_reputation(env: Env, admin: Address, user: Address, data: ReputationData) {
        admin.require_auth();
        if admin != read_admin(&env) {
            panic!("unauthorized admin");
        }
        write_reputation(&env, &user, &data);
    }

    /// Update and persist an artisan's reputation score after verifying the completed escrow.
    pub fn rate_artisan(
        env: Env,
        caller: Address,
        artisan: Address,
        stars: u64,
        escrow_contract_id: Address,
        engagement_id: u64,
    ) {
        caller.require_auth();

        if caller == artisan {
            panic!("cannot rate yourself");
        }

        if !(1..=5).contains(&stars) {
            panic!("stars not in range");
        }

        if has_caller_rated_artisan(&env, &caller, &artisan) {
            panic!("Already rated");
        }

        if has_engagement_been_rated(&env, &escrow_contract_id, engagement_id) {
            panic!("engagement already rated");
        }

        let escrow_client = EscrowVerifierClient::new(&env, &escrow_contract_id);
        let engagement = escrow_client.get_engagement(&engagement_id);

        if engagement.client != caller {
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
        artisan_data.total_stars += stars;
        artisan_data.review_count += 1;

        write_reputation(&env, &artisan, &artisan_data);
        mark_caller_rated_artisan(&env, &caller, &artisan);
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
    /// Returns (average_scaled_by_100, count).
    pub fn get_stats(env: Env, user: Address) -> (u64, u64) {
        let data = read_reputation(&env, &user);
        if data.review_count == 0 {
            return (0, 0);
        }
        let average_scaled = (data.total_stars * 100) / data.review_count;
        (average_scaled, data.review_count)
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
            material_amount: 1_000,
            labor_amount: 0,
            status,
            deadline: env.ledger().timestamp() + 1_000,
            materials_released: false,
        };

        env.as_contract(escrow_contract_id, || {
            env.storage()
                .persistent()
                .set(&EscrowDataKey::Escrow(engagement_id), &escrow);
        });
    }

    fn setup_contracts(env: &Env) -> (ReputationContractClient<'_>, Address, Address) {
        let reputation_contract_id = env.register_contract(None, ReputationContract);
        let escrow_contract_id = env.register_contract(None, EscrowContract);
        let reputation_client = ReputationContractClient::new(env, &reputation_contract_id);
        let admin = Address::generate(env);
        env.as_contract(&reputation_contract_id, || {
            env.storage().persistent().set(&DataKey::Admin, &admin);
        });
        (reputation_client, escrow_contract_id, admin)
    }

    #[test]
    fn test_default_reputation_data() {
        let default = ReputationData::default();
        assert_eq!(default.total_stars, 0);
        assert_eq!(default.review_count, 0);
    }

    #[test]
    fn test_contract_get_reputation_no_data() {
        let env = Env::default();
        let (client, _, _) = setup_contracts(&env);

        let user = Address::generate(&env);
        let reputation = client.get_reputation(&user);

        assert_eq!(reputation.total_stars, 0);
        assert_eq!(reputation.review_count, 0);
    }

    #[test]
    fn test_contract_set_and_get_reputation() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, _, admin) = setup_contracts(&env);

        let user = Address::generate(&env);
        let data = ReputationData {
            total_stars: 100,
            review_count: 20,
        };

        client.set_reputation(&admin, &user, &data);
        let retrieved = client.get_reputation(&user);

        assert_eq!(retrieved.total_stars, 100);
        assert_eq!(retrieved.review_count, 20);
    }

    #[test]
    fn test_multiple_users_independent_reputation() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, _, admin) = setup_contracts(&env);

        let user1 = Address::generate(&env);
        let user2 = Address::generate(&env);

        client.set_reputation(
            &admin,
            &user1,
            &ReputationData {
                total_stars: 50,
                review_count: 10,
            },
        );
        client.set_reputation(
            &admin,
            &user2,
            &ReputationData {
                total_stars: 75,
                review_count: 15,
            },
        );

        let retrieved1 = client.get_reputation(&user1);
        let retrieved2 = client.get_reputation(&user2);

        assert_eq!(retrieved1.total_stars, 50);
        assert_eq!(retrieved1.review_count, 10);
        assert_eq!(retrieved2.total_stars, 75);
        assert_eq!(retrieved2.review_count, 15);
    }

    #[test]
    fn test_update_existing_reputation() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, _, admin) = setup_contracts(&env);

        let user = Address::generate(&env);
        client.set_reputation(
            &admin,
            &user,
            &ReputationData {
                total_stars: 30,
                review_count: 5,
            },
        );

        client.set_reputation(
            &admin,
            &user,
            &ReputationData {
                total_stars: 80,
                review_count: 12,
            },
        );

        let retrieved = client.get_reputation(&user);
        assert_eq!(retrieved.total_stars, 80);
        assert_eq!(retrieved.review_count, 12);
    }

    #[test]
    fn test_rate_artisan_with_verified_completed_engagement() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, escrow_contract_id, _) = setup_contracts(&env);

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
        assert_eq!(reputation.total_stars, 5);
        assert_eq!(reputation.review_count, 1);
    }

    #[test]
    #[should_panic]
    fn test_rate_artisan_requires_auth() {
        let env = Env::default();
        let (client, escrow_contract_id, _) = setup_contracts(&env);

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
        let (client, escrow_contract_id, _) = setup_contracts(&env);

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
        let (client, escrow_contract_id, _) = setup_contracts(&env);

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
    #[should_panic(expected = "Already rated")]
    fn test_rate_artisan_prevents_double_rating() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, escrow_contract_id, _) = setup_contracts(&env);

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
        let (client, escrow_contract_id, _) = setup_contracts(&env);

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
        let (client, escrow_contract_id, _) = setup_contracts(&env);

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
        env.mock_all_auths();
        let (client, _, admin) = setup_contracts(&env);

        let artisan = Address::generate(&env);
        client.set_reputation(
            &admin,
            &artisan,
            &ReputationData {
                total_stars: 9,
                review_count: 2,
            },
        );

        let (average_scaled, count) = client.get_stats(&artisan);
        assert_eq!(average_scaled, 450);
        assert_eq!(count, 2);
    }

    #[test]
    #[should_panic(expected = "Already rated")]
    fn test_rate_artisan_rejects_duplicate_caller_artisan_pair() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, escrow_contract_id, _) = setup_contracts(&env);

        let caller = Address::generate(&env);
        let artisan = Address::generate(&env);

        seed_escrow(
            &env,
            &escrow_contract_id,
            1,
            &caller,
            &artisan,
            EscrowContractStatus::Released,
        );
        seed_escrow(
            &env,
            &escrow_contract_id,
            2,
            &caller,
            &artisan,
            EscrowContractStatus::Released,
        );

        client.rate_artisan(&caller, &artisan, &5, &escrow_contract_id, &1);
        client.rate_artisan(&caller, &artisan, &4, &escrow_contract_id, &2);
    }

    #[test]
    #[should_panic(expected = "cannot rate yourself")]
    fn test_rate_artisan_rejects_self_rating() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, escrow_contract_id, _) = setup_contracts(&env);

        let artisan = Address::generate(&env);
        seed_escrow(
            &env,
            &escrow_contract_id,
            1,
            &artisan,
            &artisan,
            EscrowContractStatus::Released,
        );

        client.rate_artisan(&artisan, &artisan, &5, &escrow_contract_id, &1);
    }

    #[test]
    #[should_panic]
    fn test_set_reputation_requires_admin_auth() {
        let env = Env::default();
        let (client, _, admin) = setup_contracts(&env);

        let user = Address::generate(&env);
        client.set_reputation(
            &admin,
            &user,
            &ReputationData {
                total_stars: 10,
                review_count: 2,
            },
        );
    }
}

#[cfg(test)]
mod test;
