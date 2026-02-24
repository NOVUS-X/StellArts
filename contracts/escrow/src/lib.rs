#![no_std]

use soroban_sdk::{contract, contractimpl, contracttype, token, Address, Env};

// TTL constants for persistent storage (in ledgers)
// Note: Each ledger is approximately 5 seconds
const ESCROW_TTL: u32 = 1_036_800; // ~60 days
const NEXT_ID_TTL: u32 = 6_220_800; // ~1 year
const TTL_THRESHOLD: u32 = 17_280; // ~1 day - triggers extension when TTL drops below this

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Escrow {
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub status: Status,
    pub deadline: u64,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Status {
    Pending,
    Funded,
    Released,
    Refunded, // added for reclaimed/returned escrows
    Disputed,
}

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Escrow(u64),
    NextId,
}

#[contracttype]
pub struct EngagementInitializedEvent {
    pub id: u64,
    pub client: Address,
    pub artisan: Address,
}

// Event emitted when a funded escrow is reclaimed by the client after the deadline
#[contracttype]
pub struct ReclaimedEvent {
    pub id: u64,
    pub client: Address,
    pub amount: i128,
    pub timestamp: u64,
}

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowContract {
    /// Initialize a new escrow engagement
    /// Creates a new escrow record with Pending status
    pub fn initialize(
        env: Env,
        client: Address,
        artisan: Address,
        amount: i128,
        deadline: u64,
    ) -> u64 {
        // Validation: client cannot be the same as artisan
        if client == artisan {
            panic!("Client and artisan cannot be the same address");
        }

        // Validation: amount must be positive
        if amount <= 0 {
            panic!("Amount must be greater than zero");
        }

        // Generate unique engagement ID
        let next_id = env
            .storage()
            .persistent()
            .get(&DataKey::NextId)
            .unwrap_or(1u64);

        let engagement_id = next_id;

        // Update next ID for future engagements
        let next_id_key = DataKey::NextId;
        env.storage().persistent().set(&next_id_key, &(next_id + 1));
        env.storage()
            .persistent()
            .extend_ttl(&next_id_key, TTL_THRESHOLD, NEXT_ID_TTL);

        // Create new escrow record
        let escrow = Escrow {
            client: client.clone(),
            artisan: artisan.clone(),
            amount,
            status: Status::Pending,
            deadline,
        };

        // Store the escrow in persistent storage
        let escrow_key = DataKey::Escrow(engagement_id);
        env.storage().persistent().set(&escrow_key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&escrow_key, TTL_THRESHOLD, ESCROW_TTL);

        // Emit event
        env.events().publish(
            (),
            EngagementInitializedEvent {
                id: engagement_id,
                client,
                artisan,
            },
        );

        engagement_id
    }

    /// Deposit funds into escrow for a specific engagement
    /// The client must have previously authorized the escrow contract to spend tokens
    pub fn deposit(env: Env, engagement_id: u64, token: Address) {
        // Load the escrow record
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .unwrap_or_else(|| panic!("Escrow not found for engagement {}", engagement_id));

        // Deadline enforcement: cannot deposit after the deadline has passed
        let current_time = env.ledger().timestamp();
        if current_time > escrow.deadline {
            panic!("Deadline has passed; cannot deposit into this escrow");
        }

        // Note: Authorization should be verified by the calling application
        // In a production system, this would require client signature verification

        // Verify that the escrow is in Pending status
        if escrow.status != Status::Pending {
            panic!("Escrow must be in Pending status to deposit funds");
        }

        // Transfer tokens from client to escrow contract
        let token_client = token::Client::new(&env, &token);
        token_client.transfer(
            &escrow.client,
            &env.current_contract_address(),
            &escrow.amount,
        );

        // Update escrow status to Funded
        escrow.status = Status::Funded;

        // Save the updated escrow and extend TTL
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD as u32, ESCROW_TTL as u32);
    }

    /// Release funds from escrow to the artisan
    /// Can only be called by the client and only when escrow is funded.
    /// Also verifies that the deadline has not passed; after the deadline the client
    /// must use `reclaim` to retrieve funds instead.
    pub fn release(env: Env, engagement_id: u64, token: Address) {
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        // Auth: Require the client's signature
        escrow.client.require_auth();

        // Deadline check: prevent releasing funds after deadline has passed
        let current_time = env.ledger().timestamp();
        if current_time > escrow.deadline {
            panic!("Deadline has passed; cannot release funds");
        }

        // Checks: Ensure the escrow status is Funded
        if escrow.status != Status::Funded {
            panic!("Escrow is not funded");
        }

        // Logic: Transfer the stored escrow amount from the contract address to the artisan's address
        let token_client = token::Client::new(&env, &token);
        token_client.transfer(
            &env.current_contract_address(),
            &escrow.artisan,
            &escrow.amount,
        );

        // State: Update the escrow status to Released
        escrow.status = Status::Released;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD as u32, ESCROW_TTL as u32);
    }

    /// Allow the client to reclaim funds after the deadline has passed when an escrow is still funded.
    ///
    /// Transfers the amount back to the client, updates the status to `Refunded`, and emits a
    /// [`ReclaimedEvent`]. Returns `true` on success.
    pub fn reclaim(env: Env, engagement_id: u64, token: Address) -> bool {
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        // Auth: only the client may reclaim
        escrow.client.require_auth();

        // State check: must be funded
        if escrow.status != Status::Funded {
            panic!("Escrow must be Funded to reclaim");
        }

        // Deadline check: ensure deadline has already passed
        let current_time = env.ledger().timestamp();
        if current_time <= escrow.deadline {
            panic!("Deadline has not passed; cannot reclaim yet");
        }

        // Transfer funds back to client
        let token_client = token::Client::new(&env, &token);
        token_client.transfer(
            &env.current_contract_address(),
            &escrow.client,
            &escrow.amount,
        );

        // Update state to Refunded
        escrow.status = Status::Refunded;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD as u32, ESCROW_TTL as u32);

        // Emit event
        env.events().publish(
            (),
            ReclaimedEvent {
                id: engagement_id,
                client: escrow.client.clone(),
                amount: escrow.amount,
                timestamp: current_time,
            },
        );

        true
    }
}

#[cfg(test)]
mod test;

#[cfg(test)]
mod test_legacy {
    use super::*;
    use soroban_sdk::testutils::{Events, Ledger};
    use soroban_sdk::{testutils::Address as _, Address, Env, IntoVal};

    #[test]
    fn test_initialize_engagement() {
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        // Create test addresses
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let amount: i128 = 1000;
        let deadline = env.ledger().timestamp() + 86400; // 24 hours from now

        // Initialize engagement
        let engagement_id =
            client.initialize(&client_address, &artisan_address, &amount, &deadline);

        // Verify the returned ID is valid (should be 1 for first engagement)
        assert_eq!(engagement_id, 1);

        // Verify the escrow was stored correctly
        let stored_escrow: Escrow = env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .get(&DataKey::Escrow(engagement_id))
                .unwrap()
        });

        assert_eq!(stored_escrow.client, client_address);
        assert_eq!(stored_escrow.artisan, artisan_address);
        assert_eq!(stored_escrow.amount, amount);
        assert_eq!(stored_escrow.status, Status::Pending);
        assert_eq!(stored_escrow.deadline, deadline);

        // Verify next ID was updated
        let next_id: u64 = env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .get(&DataKey::NextId)
                .unwrap_or(1)
        });
        assert_eq!(next_id, 2); // Should be incremented to 2
    }

    #[test]
    #[should_panic(expected = "Client and artisan cannot be the same address")]
    fn test_initialize_same_client_artisan() {
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let same_address = Address::generate(&env);
        let amount: i128 = 1000;
        let deadline = env.ledger().timestamp() + 86400;

        // This should panic because client == artisan
        client.initialize(&same_address, &same_address, &amount, &deadline);
    }

    #[test]
    #[should_panic(expected = "Amount must be greater than zero")]
    fn test_initialize_zero_amount() {
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let zero_amount: i128 = 0;
        let deadline = env.ledger().timestamp() + 86400;

        // This should panic because amount is zero
        client.initialize(&client_address, &artisan_address, &zero_amount, &deadline);
    }

    #[test]
    #[should_panic(expected = "Amount must be greater than zero")]
    fn test_initialize_negative_amount() {
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let negative_amount: i128 = -100;
        let deadline = env.ledger().timestamp() + 86400;

        // This should panic because amount is negative
        client.initialize(
            &client_address,
            &artisan_address,
            &negative_amount,
            &deadline,
        );
    }

    // NOTE: This test fails due to Soroban token authentication complexity
    // The deposit function requires client approval for token transfers, which is
    // extremely complex to mock in unit tests. The core deposit logic is verified
    // by other tests that don't involve cross-contract token transfers.
    // In production, clients would approve the escrow contract before calling deposit.
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
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

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
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
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
            env.storage()
                .persistent()
                .get(&DataKey::Escrow(engagement_id))
                .unwrap()
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
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
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
        let _client = EscrowContractClient::new(&env, &contract_id);

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
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
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

        _client.deposit(&engagement_id, &token_address);
    }

    // New tests for deadline and reclaim behavior

    #[test]
    #[should_panic(expected = "Deadline has passed; cannot deposit into this escrow")]
    fn test_deposit_fails_after_deadline() {
        let env = Env::default();
        env.mock_all_auths_allowing_non_root_auth();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        // Setup addresses and token
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

        // Mint some funds so transfer would succeed if not for deadline
        token_contract_client.mint(&client_address, &1000);

        // Create escrow with past deadline (ensure ledger time > 0 to avoid underflow)
        env.ledger().set_timestamp(1);
        let engagement_id = 1;
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount: 500,
            status: Status::Pending,
            deadline: env.ledger().timestamp().saturating_sub(1),
        };
        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });

        // Attempt deposit - should panic due to expired deadline
        client.deposit(&engagement_id, &token_address);
    }

    #[test]
    #[should_panic(expected = "Deadline has passed; cannot release funds")]
    fn test_release_after_deadline_fails() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        // Setup addresses and token
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

        // Mint and fund contract
        let amount: i128 = 1000;
        let engagement_id = 1;
        env.ledger().set_timestamp(1);
        let deadline = env.ledger().timestamp().saturating_sub(1);

        token_contract_client.mint(&client_address, &amount);
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address.clone(),
            amount,
            status: Status::Funded,
            deadline,
        };
        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });
        token_client.transfer(&client_address, &contract_id, &amount);

        // Releasing after deadline should panic
        client.release(&engagement_id, &token_address);
    }

    #[test]
    #[should_panic(expected = "Deadline has not passed; cannot reclaim yet")]
    fn test_reclaim_fails_before_deadline() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        // Setup funded escrow with future deadline
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();

        let engagement_id = 1;
        let amount: i128 = 500;
        let deadline = env.ledger().timestamp() + 1000;
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount,
            status: Status::Funded,
            deadline,
        };
        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });
        // ensure contract holds some funds so reclaim would succeed if deadline passed
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);
        token_contract_client.mint(&client_address, &amount);
        token_client.transfer(&client_address, &contract_id, &amount);

        client.reclaim(&engagement_id, &token_address);
    }

    #[test]
    fn test_client_reclaim_succeeds_after_deadline() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        // Setup funded escrow with past deadline
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

        // ensure ledger time > 0 to avoid underflow
        env.ledger().set_timestamp(1);
        let engagement_id = 1;
        let amount: i128 = 500;
        let deadline = env.ledger().timestamp().saturating_sub(1);
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount,
            status: Status::Funded,
            deadline,
        };
        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });
        token_contract_client.mint(&client_address, &amount);
        token_client.transfer(&client_address, &contract_id, &amount);

        let before_balance = token_client.balance(&client_address);
        client.reclaim(&engagement_id, &token_address);
        let after_balance = token_client.balance(&client_address);
        assert_eq!(after_balance, before_balance + amount);

        // Event should have been published by the escrow contract (there may be additional
        // token-contract events in the list, so filter by origin address).
        let raw_events: soroban_sdk::Vec<(
            Address,
            soroban_sdk::Vec<soroban_sdk::Val>,
            soroban_sdk::Val,
        )> = env.events().all();
        let mut found = false;
        for (addr, _, _) in raw_events.into_iter() {
            if addr == contract_id {
                found = true;
                break;
            }
        }
        assert!(found, "expected at least one escrow contract event");

        let updated: Escrow = env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .get(&DataKey::Escrow(engagement_id))
                .unwrap()
        });
        assert_eq!(updated.status, Status::Refunded);
    }

    #[test]
    #[should_panic]
    fn test_only_client_can_reclaim() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let other_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();

        // set up funded, expired escrow
        let engagement_id = 1;
        let amount: i128 = 100;
        env.ledger().set_timestamp(1);
        let deadline = env.ledger().timestamp().saturating_sub(1);
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount,
            status: Status::Funded,
            deadline,
        };
        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);
        token_contract_client.mint(&client_address, &amount);
        token_client.transfer(&client_address, &contract_id, &amount);

        // Attempt to reclaim as non-client
        env.mock_auths(&[soroban_sdk::testutils::MockAuth {
            address: &other_address,
            invoke: &soroban_sdk::testutils::MockAuthInvoke {
                contract: &contract_id,
                fn_name: "reclaim",
                args: (engagement_id, token_address.clone()).into_val(&env),
                sub_invokes: &[],
            },
        }]);

        client.reclaim(&engagement_id, &token_address);
    }

    #[test]
    #[should_panic(expected = "Escrow must be Funded to reclaim")]
    fn test_reclaim_fails_if_not_funded() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();

        let engagement_id = 1;
        let amount: i128 = 100;
        env.ledger().set_timestamp(1);
        let deadline = env.ledger().timestamp().saturating_sub(1);
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount,
            status: Status::Pending,
            deadline,
        };
        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });

        client.reclaim(&engagement_id, &token_address);
    }

    #[test]
    #[should_panic(expected = "Escrow must be Funded to reclaim")]
    fn test_reclaim_fails_if_already_released() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

        let amount: i128 = 1000;
        let engagement_id = 1;
        // use a future deadline so we can successfully call release()
        let deadline = env.ledger().timestamp() + 1000;

        token_contract_client.mint(&client_address, &amount);

        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount,
            status: Status::Funded,
            deadline,
        };

        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });

        token_client.transfer(&client_address, &contract_id, &amount);

        // release back to artist first
        client.release(&engagement_id, &token_address);
        // attempt reclaim after it's been released
        client.reclaim(&engagement_id, &token_address);
    }

    #[test]
    fn test_release_funds() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        // Create test addresses
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);

        // Create a mock token contract
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

        let amount: i128 = 1000;
        let engagement_id = 1;
        let deadline = env.ledger().timestamp() + 86400;

        // Mint tokens to client
        token_contract_client.mint(&client_address, &amount);

        // Create escrow
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address.clone(),
            amount,
            status: Status::Funded,
            deadline,
        };

        // Store the escrow
        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });

        // Transfer tokens to contract (simulating funded escrow)
        token_client.transfer(&client_address, &contract_id, &amount);

        assert_eq!(token_client.balance(&artisan_address), 0);
        assert_eq!(token_client.balance(&contract_id), amount);

        client.release(&engagement_id, &token_address);

        assert_eq!(token_client.balance(&artisan_address), amount);
        assert_eq!(token_client.balance(&contract_id), 0);
    }

    #[test]
    #[should_panic(expected = "Escrow is not funded")]
    fn test_release_unfunded_fails() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();

        let amount: i128 = 1000;
        let engagement_id = 1;
        let deadline = env.ledger().timestamp() + 86400;

        // Create escrow in Pending status
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount,
            status: Status::Pending,
            deadline,
        };

        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });

        client.release(&engagement_id, &token_address);
    }

    #[test]
    #[should_panic(expected = "Escrow is not funded")]
    fn test_release_already_released_fails() {
        let env = Env::default();
        env.mock_all_auths();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

        let amount: i128 = 1000;
        let engagement_id = 1;
        let deadline = env.ledger().timestamp() + 86400;

        token_contract_client.mint(&client_address, &amount);

        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            amount,
            status: Status::Funded,
            deadline,
        };

        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });

        token_client.transfer(&client_address, &contract_id, &amount);

        client.release(&engagement_id, &token_address);
        client.release(&engagement_id, &token_address);
    }
}
