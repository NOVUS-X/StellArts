#![cfg(test)]

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
