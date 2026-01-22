#![cfg(test)]

use super::*;
use soroban_sdk::{
    testutils::{Address as _, Ledger, MockAuth, MockAuthInvoke},
    Address, Env, IntoVal, token,
};

#[test]
fn test_refund_after_deadline() {
    let env = Env::default();
    env.mock_all_auths();

    // Setup token
    let issuer = Address::generate(&env);
    let token_contract_id = env.register_stellar_asset_contract_v2(issuer).address();
    
    let token_client = token::Client::new(&env, &token_contract_id);
    let token_admin_client = token::StellarAssetClient::new(&env, &token_contract_id);

    let client = Address::generate(&env);
    let artisan = Address::generate(&env);
    let contract_id = env.register_contract(None, EscrowContract);
    let contract_client = EscrowContractClient::new(&env, &contract_id);

    // Mint tokens to contract to simulate funded escrow
    token_admin_client.mint(&contract_id, &1000);

    let now = 1000;
    env.ledger().set_timestamp(now);

    let deadline = now - 100; // Deadline passed
    let engagement_id = 1;

    contract_client.create_escrow(
        &engagement_id,
        &client,
        &artisan,
        &token_contract_id,
        &1000,
        &deadline,
    );

    // Act
    contract_client.refund(&engagement_id);

    // Assert
    assert_eq!(token_client.balance(&client), 1000);
    assert_eq!(token_client.balance(&contract_id), 0);
}

#[test]
fn test_refund_before_deadline_fails_without_signature() {
    let env = Env::default();
    // We don't call mock_all_auths, so artisan.require_auth() should fail.

    // Setup token
    let issuer = Address::generate(&env);
    let token_contract_id = env.register_stellar_asset_contract_v2(issuer.clone()).address();
    
    let token_admin_client = token::StellarAssetClient::new(&env, &token_contract_id);

    let client = Address::generate(&env);
    let artisan = Address::generate(&env);
    let contract_id = env.register_contract(None, EscrowContract);
    let contract_client = EscrowContractClient::new(&env, &contract_id);

    // Mint with specific auth
    token_admin_client
        .mock_auths(&[
            MockAuth {
                address: &issuer,
                invoke: &MockAuthInvoke {
                    contract: &token_contract_id,
                    fn_name: "mint",
                    args: (&contract_id, 1000_i128).into_val(&env),
                    sub_invokes: &[],
                },
            },
        ])
        .mint(&contract_id, &1000);

    let now = 1000;
    env.ledger().set_timestamp(now);

    let deadline = now + 100; // Deadline in future
    let engagement_id = 1;

    contract_client.create_escrow(
        &engagement_id,
        &client,
        &artisan,
        &token_contract_id,
        &1000,
        &deadline,
    );

    // Act & Assert
    let res = contract_client.try_refund(&engagement_id);
    assert!(res.is_err());
}

#[test]
fn test_refund_before_deadline_succeeds_with_signature() {
    let env = Env::default();
    env.mock_all_auths(); // Mocks auth for everyone, so artisan signature is valid

    // Setup token
    let issuer = Address::generate(&env);
    let token_contract_id = env.register_stellar_asset_contract_v2(issuer).address();
    
    let token_client = token::Client::new(&env, &token_contract_id);
    let token_admin_client = token::StellarAssetClient::new(&env, &token_contract_id);

    let client = Address::generate(&env);
    let artisan = Address::generate(&env);
    let contract_id = env.register_contract(None, EscrowContract);
    let contract_client = EscrowContractClient::new(&env, &contract_id);

    token_admin_client.mint(&contract_id, &1000);

    let now = 1000;
    env.ledger().set_timestamp(now);

    let deadline = now + 100; // Deadline in future
    let engagement_id = 1;

    contract_client.create_escrow(
        &engagement_id,
        &client,
        &artisan,
        &token_contract_id,
        &1000,
        &deadline,
    );

    // Act
    contract_client.refund(&engagement_id);

    // Assert
    assert_eq!(token_client.balance(&client), 1000);
}
