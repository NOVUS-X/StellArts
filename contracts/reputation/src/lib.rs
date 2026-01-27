#![no_std]

use soroban_sdk::{Address, Env, contract, contractimpl, contracttype};

/// Storage key for user reputation data
#[contracttype]
#[derive(Clone)]
enum DataKey {
    Reputation(Address),
}

/// Public struct containing aggregated review data for a user
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReputationData {
    pub total_stars: u64,
    pub review_count: u64,
}

impl Default for ReputationData {
    fn default() -> Self {
        ReputationData {
            total_stars: 0,
            review_count: 0,
        }
    }
}

/// Helper function to read reputation data for a user
/// Returns default values (0 total_stars, 0 review_count) if user has no existing reputation
pub fn read_reputation(env: &Env, user: &Address) -> ReputationData {
    let key = DataKey::Reputation(user.clone());
    env.storage()
        .persistent()
        .get(&key)
        .unwrap_or_else(|| ReputationData::default())
}

/// Helper function to write reputation data for a user
/// Uses Persistent storage for all user reputation data
pub fn write_reputation(env: &Env, user: &Address, data: &ReputationData) {
    let key = DataKey::Reputation(user.clone());
    env.storage().persistent().set(&key, data);
}

#[contract]
pub struct ReputationContract;

#[contractimpl]
impl ReputationContract {
    /// Get reputation data for a user
    pub fn get_reputation(env: Env, user: Address) -> ReputationData {
        read_reputation(&env, &user)
    }

    /// Set reputation data for a user (for testing/admin purposes)
    pub fn set_reputation(env: Env, user: Address, data: ReputationData) {
        write_reputation(&env, &user, &data);
    }

    // update and persist an artisan’s reputation score
    pub fn rate_artisan(env: Env, artisan: Address, stars: u32) {
        if stars < 1 || stars > 5 {
            panic!("stars not in range");
        }
        let mut artisan_data = Self::get_reputation(env.clone(), artisan.clone());
        artisan_data.total_stars += stars as u64;
        artisan_data.review_count += 1;

        Self::set_reputation(env, artisan, artisan_data);

    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use soroban_sdk::testutils::Address as _;
    use soroban_sdk::Env;

    #[test]
    fn test_default_reputation_data() {
        let default = ReputationData::default();
        assert_eq!(default.total_stars, 0);
        assert_eq!(default.review_count, 0);
    }

    #[test]
    fn test_contract_get_reputation_no_data() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);

        let user = Address::generate(&env);
        let reputation = client.get_reputation(&user);

        // Verifies that read_reputation returns default values (0, 0) when no reputation exists
        assert_eq!(reputation.total_stars, 0);
        assert_eq!(reputation.review_count, 0);
    }

    #[test]
    fn test_contract_set_and_get_reputation() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);

        let user = Address::generate(&env);
        let data = ReputationData {
            total_stars: 100,
            review_count: 20,
        };

        // Test write_reputation helper through contract
        client.set_reputation(&user, &data);

        // Test read_reputation helper through contract
        let retrieved = client.get_reputation(&user);

        assert_eq!(retrieved.total_stars, 100);
        assert_eq!(retrieved.review_count, 20);
    }

    #[test]
    fn test_multiple_users_independent_reputation() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);

        let user1 = Address::generate(&env);
        let user2 = Address::generate(&env);

        let data1 = ReputationData {
            total_stars: 50,
            review_count: 10,
        };
        let data2 = ReputationData {
            total_stars: 75,
            review_count: 15,
        };

        client.set_reputation(&user1, &data1);
        client.set_reputation(&user2, &data2);

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
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);

        let user = Address::generate(&env);

        // Set initial reputation
        let initial_data = ReputationData {
            total_stars: 30,
            review_count: 5,
        };
        client.set_reputation(&user, &initial_data);

        // Update reputation
        let updated_data = ReputationData {
            total_stars: 80,
            review_count: 12,
        };
        client.set_reputation(&user, &updated_data);

        let retrieved = client.get_reputation(&user);
        assert_eq!(retrieved.total_stars, 80);
        assert_eq!(retrieved.review_count, 12);
    }

     #[test]
    fn test_rate_artisan() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);

        let artisan = Address::generate(&env);
        let _ = client.rate_artisan(&artisan, &2);
        let reputation = client.get_reputation(&artisan);

        // Verifies that read_reputation returns default values (0, 0) when no reputation exists
        assert_eq!(reputation.total_stars, 2);
        assert_eq!(reputation.review_count, 1);
    }

    #[test]
    #[should_panic(expected = "stars not in range")]
    fn test_rate_artisan_not_in_range() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);

        let artisan = Address::generate(&env);
        let _ = client.rate_artisan(&artisan, &6);
    }

    #[test]
    #[should_panic(expected = "stars not in range")]
    fn test_rate_artisan_not_in_range_zero() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);

        let artisan = Address::generate(&env);
        let _ = client.rate_artisan(&artisan, &0);
    }

    #[test]
    fn test_rate_artisan_multiple() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);

        let artisan = Address::generate(&env);
        let _ = client.rate_artisan(&artisan, &2);
        let _ = client.rate_artisan(&artisan, &5);
        let _ = client.rate_artisan(&artisan, &1);
        let reputation = client.get_reputation(&artisan);

        assert_eq!(reputation.total_stars, 8);
        assert_eq!(reputation.review_count, 3);
    }
}
