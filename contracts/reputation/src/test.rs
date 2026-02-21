#![cfg(test)]

use super::*;
use soroban_sdk::{testutils::Address as _, Address, Env};

#[test]
fn test_reputation_flow_integration() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);

    // Create artisan address
    let artisan = Address::generate(&env);

    // Scenario: Artisan starts with 0 reputation
    let initial_stats = client.get_stats_scaled(&artisan);
    assert_eq!(initial_stats, (0, 0)); // (average_scaled, review_count)

    // Scenario: User A submits a rating of 5 stars
    let _user_a = Address::generate(&env);
    client.rate_artisan(&artisan, &5);

    // Verify after first rating
    let stats_after_user_a = client.get_stats_scaled(&artisan);
    assert_eq!(stats_after_user_a, (500, 1)); // (500 = 5.0 * 100, 1 review)

    // Scenario: User B submits a rating of 3 stars
    let _user_b = Address::generate(&env);
    client.rate_artisan(&artisan, &3);

    // Assert that get_stats returns an average of 4.0
    let final_stats = client.get_stats(&artisan);
    assert_eq!(final_stats, (8, 2)); // (total_stars, review_count)

    // Calculate average: 8 total_stars / 2 review_count = 4.0
    let average = final_stats.0 as f64 / final_stats.1 as f64;
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

    let artisan = Address::generate(&env);

    // Edge Case: Attempt to rate with 0 stars (should panic)
    client.rate_artisan(&artisan, &0);
}

#[test]
#[should_panic(expected = "stars not in range")]
fn test_edge_case_six_stars() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);

    let artisan = Address::generate(&env);

    // Edge Case: Attempt to rate with 6 stars (should panic)
    client.rate_artisan(&artisan, &6);
}

#[test]
fn test_reputation_robustness_multiple_reviews() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);

    let artisan = Address::generate(&env);

    // Simulate a popular artisan receiving multiple reviews
    let ratings = [5, 4, 5, 3, 5, 4, 5, 5, 4, 3]; // 10 reviews

    for rating in ratings {
        client.rate_artisan(&artisan, &rating);
    }

    let stats = client.get_stats_scaled(&artisan);
    assert_eq!(stats.1, 10); // 10 reviews

    // Calculate expected total: 5+4+5+3+5+4+5+5+4+3 = 43
    assert_eq!(stats.0, 43); // 43 total stars

    // Verify average: 43 / 10 = 4.3
    let average = stats.0 as f64 / stats.1 as f64;
    assert_eq!(average, 4.3);

    // Verify no overflow with many reviews
    for _ in 0..100 {
        client.rate_artisan(&artisan, &5);
    }

    let final_stats = client.get_stats(&artisan);
    assert_eq!(final_stats.1, 110); // 110 total reviews
    // Average: (43 + 500) / 110 = 543 / 110 = 4.936... → 493 scaled
    assert_eq!(final_stats.0, 493); // 493 = 4.93 * 100 (scaled average)
}

#[test]
fn test_reputation_isolation_between_artisans() {
    let env = Env::default();
    let contract_id = env.register_contract(None, ReputationContract);
    let client = ReputationContractClient::new(&env, &contract_id);

    let artisan1 = Address::generate(&env);
    let artisan2 = Address::generate(&env);

    // Rate artisan1
    client.rate_artisan(&artisan1, &5);
    client.rate_artisan(&artisan1, &3);

    // Rate artisan2
    client.rate_artisan(&artisan2, &4);
    client.rate_artisan(&artisan2, &4);

    let stats1 = client.get_stats_scaled(&artisan1);
    let stats2 = client.get_stats_scaled(&artisan2);

    // Verify isolation: artisan1 has 8/2 = 4.0 average
    assert_eq!(stats1, (8, 2));

    // Verify isolation: artisan2 has 8/2 = 4.0 average
    assert_eq!(stats2, (8, 2));

    // But they should have different addresses (isolation)
    assert_ne!(artisan1, artisan2); // Different addresses

    // Both should have the same reputation values but stored separately
    let rep1 = client.get_reputation(&artisan1);
    let rep2 = client.get_reputation(&artisan2);
    assert_eq!(rep1.total_stars, 8);
    assert_eq!(rep2.total_stars, 8);
    assert_eq!(rep1.review_count, 2);
    assert_eq!(rep2.review_count, 2);

    // Verify that changing one doesn't affect the other
    client.rate_artisan(&artisan1, &5);
    let rep1_updated = client.get_reputation(&artisan1);
    let rep2_unchanged = client.get_reputation(&artisan2);

    assert_eq!(rep1_updated.total_stars, 13); // 8 + 5
    assert_eq!(rep1_updated.review_count, 3); // 2 + 1
    assert_eq!(rep2_unchanged.total_stars, 8); // unchanged
    assert_eq!(rep2_unchanged.review_count, 2); // unchanged
}
