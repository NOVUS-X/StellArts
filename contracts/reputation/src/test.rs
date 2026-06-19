use super::*;
use escrow::{DataKey as EscrowDataKey, Escrow, EscrowContract, Status as EscrowContractStatus};
use soroban_sdk::{testutils::Address as _, Address, Env};

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

fn setup(env: &Env) -> (ReputationContractClient<'_>, Address, Address) {
    let reputation_contract_id = env.register_contract(None, ReputationContract);
    let escrow_contract_id = env.register_contract(None, EscrowContract);
    let admin = Address::generate(env);
    env.as_contract(&reputation_contract_id, || {
        env.storage().persistent().set(&DataKey::Admin, &admin);
    });
    (
        ReputationContractClient::new(env, &reputation_contract_id),
        escrow_contract_id,
        admin,
    )
}

#[test]
fn test_reputation_flow_integration() {
    let env = Env::default();
    env.mock_all_auths();
    let (client, escrow_contract_id, _) = setup(&env);

    let artisan = Address::generate(&env);
    let client_a = Address::generate(&env);
    let client_b = Address::generate(&env);

    seed_escrow(
        &env,
        &escrow_contract_id,
        1,
        &client_a,
        &artisan,
        EscrowContractStatus::Released,
    );
    seed_escrow(
        &env,
        &escrow_contract_id,
        2,
        &client_b,
        &artisan,
        EscrowContractStatus::Resolved,
    );

    client.rate_artisan(&client_a, &artisan, &5, &escrow_contract_id, &1);
    client.rate_artisan(&client_b, &artisan, &3, &escrow_contract_id, &2);

    let stats = client.get_stats(&artisan);
    assert_eq!(stats, (400, 2));

    let reputation = client.get_reputation(&artisan);
    assert_eq!(reputation.total_stars, 8);
    assert_eq!(reputation.review_count, 2);
}

#[test]
fn test_reputation_robustness_multiple_reviews() {
    let env = Env::default();
    env.mock_all_auths();
    let (client, escrow_contract_id, _) = setup(&env);

    let artisan = Address::generate(&env);
    let ratings = [5, 4, 5, 3, 5, 4, 5, 5, 4, 3];

    for (index, rating) in ratings.iter().enumerate() {
        let reviewer = Address::generate(&env);
        let engagement_id = index as u64 + 1;
        seed_escrow(
            &env,
            &escrow_contract_id,
            engagement_id,
            &reviewer,
            &artisan,
            EscrowContractStatus::Released,
        );
        client.rate_artisan(
            &reviewer,
            &artisan,
            rating,
            &escrow_contract_id,
            &engagement_id,
        );
    }

    let stats = client.get_stats(&artisan);
    assert_eq!(stats.1, 10);
    assert_eq!(stats.0, 430);

    let reputation = client.get_reputation(&artisan);
    assert_eq!(reputation.total_stars, 43);
    assert_eq!(reputation.review_count, 10);
}

#[test]
fn test_reputation_isolation_between_artisans() {
    let env = Env::default();
    env.mock_all_auths();
    let (client, escrow_contract_id, _) = setup(&env);

    let artisan1 = Address::generate(&env);
    let artisan2 = Address::generate(&env);

    let client_1a = Address::generate(&env);
    let client_1b = Address::generate(&env);
    let client_2a = Address::generate(&env);

    seed_escrow(
        &env,
        &escrow_contract_id,
        1,
        &client_1a,
        &artisan1,
        EscrowContractStatus::Released,
    );
    seed_escrow(
        &env,
        &escrow_contract_id,
        2,
        &client_1b,
        &artisan1,
        EscrowContractStatus::Released,
    );
    seed_escrow(
        &env,
        &escrow_contract_id,
        3,
        &client_2a,
        &artisan2,
        EscrowContractStatus::Resolved,
    );

    client.rate_artisan(&client_1a, &artisan1, &5, &escrow_contract_id, &1);
    client.rate_artisan(&client_1b, &artisan1, &3, &escrow_contract_id, &2);
    client.rate_artisan(&client_2a, &artisan2, &4, &escrow_contract_id, &3);

    assert_eq!(client.get_stats(&artisan1), (400, 2));
    assert_eq!(client.get_stats(&artisan2), (400, 1));

    let rep1 = client.get_reputation(&artisan1);
    let rep2 = client.get_reputation(&artisan2);
    assert_eq!(rep1.total_stars, 8);
    assert_eq!(rep1.review_count, 2);
    assert_eq!(rep2.total_stars, 4);
    assert_eq!(rep2.review_count, 1);
}
