
import os

lib_rs_path = r"c:\Users\delig\StellArts-contract\contracts\reputation\src\lib.rs"
test_rs_path = r"c:\Users\delig\StellArts-contract\contracts\reputation\src\test.rs"

# Rewrite lib.rs
lib_rs_content = """#![no_std]

use soroban_sdk::{contract, contractimpl, contracttype, Address, Env};

/// Storage key for user reputation data
#[contracttype]
#[derive(Clone)]
enum DataKey {
    Reputation(Address),
    Admin,
    HasRated(Address, Address),
}

#[contracttype]
pub struct RateArtisanEvent {
    pub artisan: Address,
    pub stars: u64,
    pub timestamp: u64,
}

/// Public struct containing aggregated review data for a user
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq, Default)]
pub struct ReputationData {
    pub total_stars: u64,
    pub review_count: u64,
}

pub fn read_reputation(env: &Env, user: &Address) -> ReputationData {
    let key = DataKey::Reputation(user.clone());
    env.storage()
        .persistent()
        .get(&key)
        .unwrap_or_default()
}

pub fn write_reputation(env: &Env, user: &Address, data: &ReputationData) {
    let key = DataKey::Reputation(user.clone());
    env.storage().persistent().set(&key, data);
}

#[contract]
pub struct ReputationContract;

#[contractimpl]
impl ReputationContract {
    pub fn initialize(env: Env, admin: Address) {
        let key = DataKey::Admin;
        if env.storage().persistent().has(&key) {
            panic!("Already initialized");
        }
        env.storage().persistent().set(&key, &admin);
    }

    pub fn get_reputation(env: Env, user: Address) -> ReputationData {
        read_reputation(&env, &user)
    }

    pub fn set_reputation(env: Env, admin: Address, user: Address, data: ReputationData) {
        admin.require_auth();
        let expected_admin: Address = env.storage().persistent().get(&DataKey::Admin).expect("Admin not set");
        if admin != expected_admin {
            panic!("Unauthorized admin");
        }
        write_reputation(&env, &user, &data);
    }

    pub fn rate_artisan(env: Env, caller: Address, artisan: Address, stars: u64) {
        caller.require_auth();
        if caller == artisan {
            panic!("Self-rating is not allowed");
        }

        let dedupe_key = DataKey::HasRated(caller.clone(), artisan.clone());
        if env.storage().persistent().has(&dedupe_key) {
            panic!("Already rated");
        }
        env.storage().persistent().set(&dedupe_key, &true);

        if !(1..=5).contains(&stars) {
            panic!("stars not in range");
        }
        
        // bypass set_reputation since it requires admin
        let mut artisan_data = read_reputation(&env, &artisan);
        artisan_data.total_stars += stars;
        artisan_data.review_count += 1;

        write_reputation(&env, &artisan, &artisan_data);

        env.events().publish(
            (),
            RateArtisanEvent {
                artisan,
                stars,
                timestamp: env.ledger().timestamp(),
            },
        );
    }

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

        assert_eq!(reputation.total_stars, 0);
        assert_eq!(reputation.review_count, 0);
    }

    #[test]
    fn test_contract_set_and_get_reputation() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();

        let admin = Address::generate(&env);
        client.initialize(&admin);

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
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();
        
        let admin = Address::generate(&env);
        client.initialize(&admin);

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

        client.set_reputation(&admin, &user1, &data1);
        client.set_reputation(&admin, &user2, &data2);

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
        env.mock_all_auths();

        let admin = Address::generate(&env);
        client.initialize(&admin);

        let user = Address::generate(&env);

        let initial_data = ReputationData {
            total_stars: 30,
            review_count: 5,
        };
        client.set_reputation(&admin, &user, &initial_data);

        let updated_data = ReputationData {
            total_stars: 80,
            review_count: 12,
        };
        client.set_reputation(&admin, &user, &updated_data);

        let retrieved = client.get_reputation(&user);
        assert_eq!(retrieved.total_stars, 80);
        assert_eq!(retrieved.review_count, 12);
    }

    #[test]
    fn test_rate_artisan() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();

        let caller = Address::generate(&env);
        let artisan = Address::generate(&env);
        let _ = client.rate_artisan(&caller, &artisan, &2);
        let reputation = client.get_reputation(&artisan);

        assert_eq!(reputation.total_stars, 2);
        assert_eq!(reputation.review_count, 1);
    }

    #[test]
    #[should_panic(expected = "stars not in range")]
    fn test_rate_artisan_not_in_range() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();

        let caller = Address::generate(&env);
        let artisan = Address::generate(&env);
        let _ = client.rate_artisan(&caller, &artisan, &6);
    }

    #[test]
    #[should_panic(expected = "stars not in range")]
    fn test_rate_artisan_not_in_range_zero() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();

        let caller = Address::generate(&env);
        let artisan = Address::generate(&env);
        let _ = client.rate_artisan(&caller, &artisan, &0);
    }

    #[test]
    fn test_rate_artisan_multiple() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();

        let caller1 = Address::generate(&env);
        let caller2 = Address::generate(&env);
        let caller3 = Address::generate(&env);
        let artisan = Address::generate(&env);
        
        let _ = client.rate_artisan(&caller1, &artisan, &2);
        let _ = client.rate_artisan(&caller2, &artisan, &5);
        let _ = client.rate_artisan(&caller3, &artisan, &1);
        let reputation = client.get_reputation(&artisan);

        assert_eq!(reputation.total_stars, 8);
        assert_eq!(reputation.review_count, 3);
    }

    #[test]
    fn test_get_stats() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();

        let admin = Address::generate(&env);
        client.initialize(&admin);

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
    #[should_panic]
    fn test_rate_without_auth() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        
        let caller = Address::generate(&env);
        let artisan = Address::generate(&env);
        client.rate_artisan(&caller, &artisan, &5);
    }

    #[test]
    #[should_panic(expected = "Already rated")]
    fn test_rate_duplicate() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();
        
        let caller = Address::generate(&env);
        let artisan = Address::generate(&env);
        client.rate_artisan(&caller, &artisan, &5);
        client.rate_artisan(&caller, &artisan, &4);
    }

    #[test]
    #[should_panic(expected = "Self-rating is not allowed")]
    fn test_rate_self() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();
        
        let caller_artisan = Address::generate(&env);
        client.rate_artisan(&caller_artisan, &caller_artisan, &5);
    }

    #[test]
    #[should_panic]
    fn test_set_reputation_without_auth() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        
        let admin = Address::generate(&env);
        client.initialize(&admin);
        
        let user = Address::generate(&env);
        let data = ReputationData { total_stars: 5, review_count: 1 };
        client.set_reputation(&admin, &user, &data);
    }

    #[test]
    #[should_panic(expected = "Unauthorized admin")]
    fn test_set_reputation_wrong_admin() {
        let env = Env::default();
        let contract_id = env.register_contract(None, ReputationContract);
        let client = ReputationContractClient::new(&env, &contract_id);
        env.mock_all_auths();
        
        let admin = Address::generate(&env);
        client.initialize(&admin);
        
        let wrong_admin = Address::generate(&env);
        let user = Address::generate(&env);
        let data = ReputationData { total_stars: 5, review_count: 1 };
        client.set_reputation(&wrong_admin, &user, &data);
    }
}

#[cfg(test)]
mod test;
"""

test_rs_content = """#![cfg(test)]

use super::*;
use soroban_sdk::{testutils::Address as _, Address, Env};

#[test]
fn test_reputation_flow_integration() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);
    env.mock_all_auths();

    // Create artisan address
    let artisan = Address::generate(&env);

    // Scenario: Artisan starts with 0 reputation
    let initial_stats = client.get_stats(&artisan);
    assert_eq!(initial_stats, (0, 0)); // (total_stars, review_count)

    // Scenario: User A submits a rating of 5 stars
    let user_a = Address::generate(&env);
    client.rate_artisan(&user_a, &artisan, &5);

    // Verify after first rating
    let stats_after_user_a = client.get_stats(&artisan);
    assert_eq!(stats_after_user_a, (500, 1)); // (average_scaled_by_100, review_count)

    // Scenario: User B submits a rating of 3 stars
    let user_b = Address::generate(&env);
    client.rate_artisan(&user_b, &artisan, &3);

    // Assert that get_stats returns an average of 4.0
    let final_stats = client.get_stats(&artisan);
    assert_eq!(final_stats, (400, 2)); // (average_scaled_by_100, review_count)

    // Calculate average: 400 / 100 = 4.0
    let average = final_stats.0 as f64 / 100.0;
    assert_eq!(average, 4.0);

    // Verify reputation data is consistent
    let reputation = client.get_reputation(&artisan);
    assert_eq!(reputation.total_stars, 8);
    assert_eq!(reputation.review_count, 2);
}

#[test]
#[should_panic(expected = "stars not in range")]
fn test_edge_case_zero_stars() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);
    env.mock_all_auths();

    let caller = Address::generate(&env);
    let artisan = Address::generate(&env);

    client.rate_artisan(&caller, &artisan, &0);
}

#[test]
#[should_panic(expected = "stars not in range")]
fn test_edge_case_six_stars() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);
    env.mock_all_auths();

    let caller = Address::generate(&env);
    let artisan = Address::generate(&env);

    client.rate_artisan(&caller, &artisan, &6);
}

#[test]
fn test_reputation_robustness_multiple_reviews() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);
    env.mock_all_auths();

    let artisan = Address::generate(&env);

    let ratings = [5, 4, 5, 3, 5, 4, 5, 5, 4, 3]; // 10 reviews

    for rating in ratings {
        let caller = Address::generate(&env);
        client.rate_artisan(&caller, &artisan, &rating);
    }

    let stats = client.get_stats(&artisan);
    assert_eq!(stats.1, 10); // 10 reviews
    assert_eq!(stats.0, 430); // 430 = 4.3 * 100

    // Verify average: 430 / 100 = 4.3
    let average = stats.0 as f64 / 100.0;
    assert_eq!(average, 4.3);

    // Verify no overflow with many reviews
    for _ in 0..100 {
        let caller = Address::generate(&env);
        client.rate_artisan(&caller, &artisan, &5);
    }

    let final_stats = client.get_stats(&artisan);
    assert_eq!(final_stats.1, 110); // 110 total reviews
    assert_eq!(final_stats.0, 493); // (43 + 500) * 100 / 110 = 493 (scaled average)
}

#[test]
fn test_reputation_isolation_between_artisans() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);
    env.mock_all_auths();

    let artisan1 = Address::generate(&env);
    let artisan2 = Address::generate(&env);

    let caller1 = Address::generate(&env);
    let caller2 = Address::generate(&env);
    let caller3 = Address::generate(&env);
    let caller4 = Address::generate(&env);

    // Rate artisan1
    client.rate_artisan(&caller1, &artisan1, &5);
    client.rate_artisan(&caller2, &artisan1, &3);

    // Rate artisan2
    client.rate_artisan(&caller3, &artisan2, &4);
    client.rate_artisan(&caller4, &artisan2, &4);

    let stats1 = client.get_stats(&artisan1);
    let stats2 = client.get_stats(&artisan2);

    assert_eq!(stats1, (400, 2));
    assert_eq!(stats2, (400, 2));
    assert_ne!(artisan1, artisan2);

    let rep1 = client.get_reputation(&artisan1);
    let rep2 = client.get_reputation(&artisan2);
    assert_eq!(rep1.total_stars, 8);
    assert_eq!(rep2.total_stars, 8);
    assert_eq!(rep1.review_count, 2);
    assert_eq!(rep2.review_count, 2);

    let caller5 = Address::generate(&env);
    client.rate_artisan(&caller5, &artisan1, &5);
    
    let rep1_updated = client.get_reputation(&artisan1);
    let rep2_unchanged = client.get_reputation(&artisan2);

    assert_eq!(rep1_updated.total_stars, 13);
    assert_eq!(rep1_updated.review_count, 3);
    assert_eq!(rep2_unchanged.total_stars, 8);
    assert_eq!(rep2_unchanged.review_count, 2);
}
"""

with open(lib_rs_path, "w", encoding="utf-8") as f:
    f.write(lib_rs_content)
    
with open(test_rs_path, "w", encoding="utf-8") as f:
    f.write(test_rs_content)

print("Files updated successfully!")

