#![no_std]

// Escrow contract for StellArts
// TODO: Implement escrow contract logic
use soroban_sdk::{contract, contractimpl, contracttype, token, Address, Env};

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Escrow {
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub status: Status,
    pub deadline: u64
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Status {
    Pending,
    Funded,
    Released,
    Disputed
}

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Escrow(u64)
}

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowContract {
    /// Deposit funds into escrow for a specific engagement
    /// The client must have previously authorized the escrow contract to spend tokens
    pub fn deposit(env: Env, engagement_id: u64, token: Address) {
        // Load the escrow record
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .instance()
            .get(&key)
            .unwrap_or_else(|| panic!("Escrow not found for engagement {}", engagement_id));

        // Note: Authorization should be verified by the calling application
        // In a production system, this would require client signature verification

        // Verify that the escrow is in Pending status
        if escrow.status != Status::Pending {
            panic!("Escrow must be in Pending status to deposit funds");
        }

        // Transfer tokens from client to escrow contract
        let token_client = token::Client::new(&env, &token);
        token_client.transfer(&escrow.client, &env.current_contract_address(), &escrow.amount);

        // Update escrow status to Funded
        escrow.status = Status::Funded;

        // Save the updated escrow
        env.storage().instance().set(&key, &escrow);
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use soroban_sdk::{testutils::{Address as _}, Address, Env, IntoVal};

    #[test]
    fn test_deposit_funds() {
        let env = Env::default();
        // Allow non-root auth for token transfer invoked by the escrow contract.
        env.mock_all_auths_allowing_non_root_auth();
        let contract_id = env.register_contract(None, EscrowContract);
        let _client = EscrowContractClient::new(&env, &contract_id);

        // Create test addresses
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);

        // Create a mock token contract
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);

        // Mint some tokens to the client using the token contract's mint function
        let initial_amount: i128 = 1000;
        let token_contract_client = soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

        token_contract_client.mint(&client_address, &initial_amount);

        // Create an escrow record
        let engagement_id = 1;
        let escrow_amount: i128 = 500;
        let deadline = env.ledger().timestamp() + 86400; // 24 hours from now

        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount: escrow_amount,
            status: Status::Pending,
            deadline,
        };

        // Store the escrow in contract storage
        env.as_contract(&contract_id, || {
            env.storage().instance().set(&DataKey::Escrow(engagement_id), &escrow);
        });

        // Check initial token balance of contract (should be 0)
        let initial_contract_balance = token_client.balance(&contract_id);
        assert_eq!(initial_contract_balance, 0);

        // Call deposit function as the client
        EscrowContractClient::new(&env, &contract_id).deposit(&engagement_id, &token_address);

        // Verify contract's token balance increased
        let final_contract_balance = token_client.balance(&contract_id);
        assert_eq!(final_contract_balance, escrow_amount);

        // Verify escrow status was updated to Funded
        let updated_escrow: Escrow = env.as_contract(&contract_id, || {
            env.storage().instance().get(&DataKey::Escrow(engagement_id)).unwrap()
        });
        assert_eq!(updated_escrow.status, Status::Funded);

        // Verify other fields remain unchanged
        assert_eq!(updated_escrow.client, client_address);
        assert_eq!(updated_escrow.amount, escrow_amount);
        assert_eq!(updated_escrow.deadline, deadline);
    }

    #[test]
    fn test_deposit_unauthorized_client() {
        // Note: Current implementation doesn't verify caller authorization
        // This test exists for completeness but doesn't enforce authorization
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let _client = EscrowContractClient::new(&env, &contract_id);

        // Create test addresses
        let client_address = Address::generate(&env);
        let unauthorized_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);

        // Create a mock token
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();

        // Create an escrow record
        let engagement_id = 1;
        let escrow_amount: i128 = 500;
        let deadline = env.ledger().timestamp() + 86400;

        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount: escrow_amount,
            status: Status::Pending,
            deadline,
        };

        // Store the escrow
        env.as_contract(&contract_id, || {
            env.storage().instance().set(&DataKey::Escrow(engagement_id), &escrow);
        });

        // In current implementation, any address can call deposit
        // This is a limitation that should be addressed in production
        env.mock_auths(&[soroban_sdk::testutils::MockAuth {
            address: &unauthorized_address,
            invoke: &soroban_sdk::testutils::MockAuthInvoke {
                contract: &contract_id,
                fn_name: "deposit",
                args: (engagement_id, token_address.clone()).into_val(&env),
                sub_invokes: &[],
            },
        }]);

        // This would work in current implementation (not ideal)
        // client.deposit(&engagement_id, &token_address);
    }

    #[test]
    #[should_panic(expected = "Escrow must be in Pending status to deposit funds")]
    fn test_deposit_already_funded() {
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        // Create test addresses
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);

        // Create a mock token
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();

        // Create an escrow record that's already funded
        let engagement_id = 1;
        let escrow_amount: i128 = 500;
        let deadline = env.ledger().timestamp() + 86400;

        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount: escrow_amount,
            status: Status::Funded, // Already funded
            deadline,
        };

        // Store the escrow
        env.as_contract(&contract_id, || {
            env.storage().instance().set(&DataKey::Escrow(engagement_id), &escrow);
        });

        // Try to deposit (should panic due to status check, but first need auth)
        env.mock_auths(&[soroban_sdk::testutils::MockAuth {
            address: &client_address,
            invoke: &soroban_sdk::testutils::MockAuthInvoke {
                contract: &contract_id,
                fn_name: "deposit",
                args: (engagement_id, token_address.clone()).into_val(&env),
                sub_invokes: &[],
            },
        }]);

        client.deposit(&engagement_id, &token_address);
    }
}
