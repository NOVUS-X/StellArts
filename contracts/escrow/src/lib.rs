#![no_std]

use soroban_sdk::{contract, contractimpl, contracttype, token, Address, Env};

// TTL constants for persistent storage (in ledgers)
// Note: Each ledger is approximately 5 seconds
const ESCROW_TTL: u32 = 1_036_800; // ~60 days
const NEXT_ID_TTL: u32 = 6_220_800; // ~1 year
const TTL_THRESHOLD: u32 = 17_280; // ~1 day - triggers extension when TTL drops below this
const GRACE_PERIOD: u64 = 86_400; // 24 hours in seconds - artisan protection window after deadline

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Escrow {
    pub client: Address,
    pub artisan: Address,
    pub arbitrator: Address,
    pub amount: i128,
    pub status: Status,
    pub deadline: u64,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DeadlineExtension {
    pub new_deadline: u64,
    pub proposer: Address,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Status {
    Pending,
    Funded,
    InProgress,
    Released,
    Refunded, // added for reclaimed/returned escrows
    Disputed,
    Resolved, // dispute resolved with split distribution
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EarlyReclaimApproval {
    pub proposer: Address,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DataKey {
    Escrow(u64),
    DeadlineExtension(u64),
    EarlyReclaim(u64),
    NextId,
    Oracle,
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

// Event emitted when a dispute is initiated on an escrow
#[contracttype]
pub struct DisputeInitiatedEvent {
    pub id: u64,
    pub initiator: Address,
    pub timestamp: u64,
}

// Event emitted when an arbitrator resolves a dispute
#[contracttype]
pub struct DisputeResolvedEvent {
    pub id: u64,
    pub client_amount: i128,
    pub artisan_amount: i128,
    pub timestamp: u64,
}

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowContract {
    /// Initialize a new escrow engagement
    /// Creates a new escrow record with Pending status and a per-escrow arbitrator
    pub fn initialize(
        env: Env,
        client: Address,
        artisan: Address,
        arbitrator: Address,
        amount: i128,
        deadline: u64,
    ) -> u64 {
        // Validation: client cannot be the same as artisan
        if client == artisan {
            panic!("Client and artisan cannot be the same address");
        }

        // Validation: arbitrator must be a distinct third party
        if arbitrator == client || arbitrator == artisan {
            panic!("Arbitrator must be different from client and artisan");
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

        // Create new escrow record with per-escrow arbitrator
        let escrow = Escrow {
            client: client.clone(),
            artisan: artisan.clone(),
            arbitrator,
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
        // Auth: Require the client's signature
        escrow.client.require_auth();

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
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);
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

        // Checks: Ensure the escrow status is Funded or InProgress
        if escrow.status != Status::Funded && escrow.status != Status::InProgress {
            panic!("Escrow is not funded or in progress");
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
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);
    }

    /// Allow the client to reclaim funds after the deadline + grace period has passed,
    /// or after the deadline if both parties have mutually approved an early reclaim.
    ///
    /// The grace period (24 hours) protects artisans from malicious reclaims when work
    /// is nearly finished. Both parties can bypass it via `approve_early_reclaim()`.
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

        // Deadline + grace period check
        let current_time = env.ledger().timestamp();
        if current_time <= escrow.deadline {
            panic!("Deadline has not passed; cannot reclaim yet");
        }

        // Check if we're still within the grace period
        let grace_deadline = escrow.deadline + GRACE_PERIOD;
        if current_time <= grace_deadline {
            // Within grace period: only allow if both parties approved early reclaim
            let early_reclaim_key = DataKey::EarlyReclaim(engagement_id);
            let has_early_approval: bool = env
                .storage()
                .persistent()
                .get::<DataKey, bool>(&early_reclaim_key)
                .unwrap_or(false);

            if !has_early_approval {
                panic!("Grace period has not passed; both parties must approve early reclaim");
            }

            // Clean up the early reclaim approval
            env.storage().persistent().remove(&early_reclaim_key);
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
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

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

    /// Mutually approve an early reclaim during the grace period.
    /// Both client and artisan must call this function to approve.
    /// Once both approve, the client can call `reclaim()` during the grace period.
    pub fn approve_early_reclaim(env: Env, engagement_id: u64, approver: Address) {
        let key = DataKey::Escrow(engagement_id);
        let escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        approver.require_auth();

        // Only client or artisan can approve
        if approver != escrow.client && approver != escrow.artisan {
            panic!("Only client or artisan can approve early reclaim");
        }

        // State check: must be funded
        if escrow.status != Status::Funded {
            panic!("Escrow must be Funded to approve early reclaim");
        }

        let early_reclaim_key = DataKey::EarlyReclaim(engagement_id);
        let pending: Option<EarlyReclaimApproval> =
            env.storage().persistent().get(&early_reclaim_key);

        if let Some(approval) = pending {
            // Second approver — must be different party
            if approval.proposer == approver {
                panic!("Same party cannot approve early reclaim twice");
            }

            // Both parties agree: store a simple bool flag
            env.storage()
                .persistent()
                .set(&early_reclaim_key, &true);
            env.storage()
                .persistent()
                .extend_ttl(&early_reclaim_key, TTL_THRESHOLD, ESCROW_TTL);
        } else {
            // First approver — store the proposal
            let approval = EarlyReclaimApproval { proposer: approver };
            env.storage()
                .persistent()
                .set(&early_reclaim_key, &approval);
            env.storage()
                .persistent()
                .extend_ttl(&early_reclaim_key, TTL_THRESHOLD, ESCROW_TTL);
        }
    }

    /// Mutually approve and apply an escrow deadline extension.
    pub fn extend_deadline(env: Env, engagement_id: u64, approver: Address, new_deadline: u64) {
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        approver.require_auth();

        if approver != escrow.client && approver != escrow.artisan {
            panic!("Only client or artisan can approve deadline extension");
        }

        if escrow.status != Status::Funded && escrow.status != Status::InProgress {
            panic!("Escrow must be Funded or InProgress to extend deadline");
        }

        if new_deadline <= escrow.deadline {
            panic!("New deadline must be greater than current deadline");
        }

        let extension_key = DataKey::DeadlineExtension(engagement_id);
        let pending: Option<DeadlineExtension> = env.storage().persistent().get(&extension_key);

        if let Some(extension) = pending {
            if extension.proposer == approver {
                panic!("Same party cannot approve deadline extension twice");
            }

            if extension.new_deadline != new_deadline {
                panic!("Pending deadline extension does not match requested deadline");
            }

            escrow.deadline = new_deadline;
            env.storage().persistent().set(&key, &escrow);
            env.storage()
                .persistent()
                .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);
            env.storage().persistent().remove(&extension_key);
        } else {
            let extension = DeadlineExtension {
                new_deadline,
                proposer: approver,
            };
            env.storage().persistent().set(&extension_key, &extension);
            env.storage()
                .persistent()
                .extend_ttl(&extension_key, TTL_THRESHOLD, ESCROW_TTL);
        }
    }

    /// Set the oracle address for verifying physical arrival
    pub fn set_oracle(env: Env, admin: Address, oracle: Address) {
        admin.require_auth();
        env.storage().persistent().set(&DataKey::Oracle, &oracle);
        env.storage()
            .persistent()
            .extend_ttl(&DataKey::Oracle, TTL_THRESHOLD, NEXT_ID_TTL);
    }

    /// Transition escrow status from Funded to InProgress
    pub fn start_job(env: Env, engagement_id: u64) {
        let oracle: Address = env
            .storage()
            .persistent()
            .get(&DataKey::Oracle)
            .expect("Oracle not set");
        oracle.require_auth();

        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        if escrow.status != Status::Funded {
            panic!("Escrow must be Funded to transition to InProgress");
        }

        escrow.status = Status::InProgress;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);
    }



    /// Initiate a dispute on a funded escrow
    /// Can be called by either the client or artisan
    /// Transitions the escrow from Funded to Disputed status
    pub fn dispute(env: Env, engagement_id: u64, initiator: Address) {
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        // Auth: Require initiator to authorize invocation
        initiator.require_auth();

        // Auth: Only client or artisan can initiate a dispute
        if initiator != escrow.client && initiator != escrow.artisan {
            panic!("Only client or artisan can initiate a dispute");
        }

        // State check: escrow must be Funded or InProgress to dispute
        if escrow.status != Status::Funded && escrow.status != Status::InProgress {
            panic!("Escrow must be Funded or InProgress to initiate a dispute");
        }

        // Transition status to Disputed
        escrow.status = Status::Disputed;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        // Emit event
        let current_time = env.ledger().timestamp();
        env.events().publish(
            (),
            DisputeInitiatedEvent {
                id: engagement_id,
                initiator,
                timestamp: current_time,
            },
        );
    }

    /// Resolve a dispute by the per-escrow arbitrator
    /// Only callable by the arbitrator assigned at escrow initialization
    /// Supports split distribution: funds can be divided between client and artisan
    /// The sum of client_amount and artisan_amount must equal the escrowed amount
    pub fn resolve_dispute(
        env: Env,
        engagement_id: u64,
        client_amount: i128,
        artisan_amount: i128,
        token: Address,
    ) {
        // Load escrow
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        // Auth: Require the per-escrow arbitrator's authorization
        escrow.arbitrator.require_auth();

        // State check: escrow must be in Disputed status
        if escrow.status != Status::Disputed {
            panic!("Escrow must be in Disputed status to resolve");
        }

        // Validation: amounts must be non-negative
        if client_amount < 0 || artisan_amount < 0 {
            panic!("Distribution amounts must be non-negative");
        }

        // Validation: distribution must equal total escrow amount
        if client_amount + artisan_amount != escrow.amount {
            panic!("Distribution amounts must equal the escrowed amount");
        }

        // Transfer funds according to distribution
        let token_client = token::Client::new(&env, &token);

        if client_amount > 0 {
            token_client.transfer(
                &env.current_contract_address(),
                &escrow.client,
                &client_amount,
            );
        }

        if artisan_amount > 0 {
            token_client.transfer(
                &env.current_contract_address(),
                &escrow.artisan,
                &artisan_amount,
            );
        }

        // Update status based on distribution
        if artisan_amount == 0 {
            // 100% to client = refund
            escrow.status = Status::Refunded;
        } else if client_amount == 0 {
            // 100% to artisan = release
            escrow.status = Status::Released;
        } else {
            // Split distribution
            escrow.status = Status::Resolved;
        }

        // Save updated escrow
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        // Emit event
        let current_time = env.ledger().timestamp();
        env.events().publish(
            (),
            DisputeResolvedEvent {
                id: engagement_id,
                client_amount,
                artisan_amount,
                timestamp: current_time,
            },
        );
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
        let arbitrator_address = Address::generate(&env);
        let amount: i128 = 1000;
        let deadline = env.ledger().timestamp() + 86400; // 24 hours from now

        // Initialize engagement
        let engagement_id =
            client.initialize(&client_address, &artisan_address, &arbitrator_address, &amount, &deadline);

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
        let arbitrator_address = Address::generate(&env);
        let amount: i128 = 1000;
        let deadline = env.ledger().timestamp() + 86400;

        // This should panic because client == artisan
        client.initialize(&same_address, &same_address, &arbitrator_address, &amount, &deadline);
    }

    #[test]
    #[should_panic(expected = "Amount must be greater than zero")]
    fn test_initialize_zero_amount() {
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let arbitrator_address = Address::generate(&env);
        let zero_amount: i128 = 0;
        let deadline = env.ledger().timestamp() + 86400;

        // This should panic because amount is zero
        client.initialize(&client_address, &artisan_address, &arbitrator_address, &zero_amount, &deadline);
    }

    #[test]
    #[should_panic(expected = "Amount must be greater than zero")]
    fn test_initialize_negative_amount() {
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let arbitrator_address = Address::generate(&env);
        let negative_amount: i128 = -100;
        let deadline = env.ledger().timestamp() + 86400;

        // This should panic because amount is negative
        client.initialize(
            &client_address,
            &artisan_address,
            &arbitrator_address,
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
            arbitrator: Address::generate(&env),
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
    #[should_panic]
    fn test_deposit_unauthorized_client() {
        let env = Env::default();
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(&env, &contract_id);

        // Create test addresses
        let client_address = Address::generate(&env);
        let unauthorized_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);

        // Create a mock token and mint tokens to the client so the test
        // doesn't fail on insufficient balance before reaching the auth check
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);
        token_contract_client.mint(&client_address, &1000i128);

        // Create an escrow record owned by client_address
        let engagement_id = 1;
        let escrow_amount: i128 = 500;
        let deadline = env.ledger().timestamp() + 86400;

        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            arbitrator: Address::generate(&env),
            amount: escrow_amount,
            status: Status::Pending,
            deadline,
        };

        env.as_contract(&contract_id, || {
            env.storage()
                .persistent()
                .set(&DataKey::Escrow(engagement_id), &escrow);
        });

        // Mock auth for the WRONG address — unauthorized_address is not the client
        env.mock_auths(&[soroban_sdk::testutils::MockAuth {
            address: &unauthorized_address,
            invoke: &soroban_sdk::testutils::MockAuthInvoke {
                contract: &contract_id,
                fn_name: "deposit",
                args: (engagement_id, token_address.clone()).into_val(&env),
                sub_invokes: &[],
            },
        }]);

        // This must panic — unauthorized_address cannot satisfy escrow.client.require_auth()
        client.deposit(&engagement_id, &token_address);
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
            arbitrator: Address::generate(&env),
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
            arbitrator: Address::generate(&env),
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
            arbitrator: Address::generate(&env),
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
            arbitrator: Address::generate(&env),
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

        // Setup funded escrow with past deadline + grace period
        let client_address = Address::generate(&env);
        let artisan_address = Address::generate(&env);
        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
        let token_address = token_contract.address();
        let token_client = soroban_sdk::token::Client::new(&env, &token_address);
        let token_contract_client =
            soroban_sdk::token::StellarAssetClient::new(&env, &token_address);

        // Set deadline in the past and timestamp beyond deadline + GRACE_PERIOD (86400s)
        let deadline = 100;
        env.ledger().set_timestamp(deadline + 86400 + 1);
        let engagement_id = 1;
        let amount: i128 = 500;
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            arbitrator: Address::generate(&env),
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

        // set up funded, expired escrow past grace period
        let engagement_id = 1;
        let amount: i128 = 100;
        let deadline = 100;
        env.ledger().set_timestamp(deadline + 86400 + 1);
        let escrow = Escrow {
            client: client_address.clone(),
            artisan: artisan_address,
            arbitrator: Address::generate(&env),
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
            arbitrator: Address::generate(&env),
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
            arbitrator: Address::generate(&env),
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
            arbitrator: Address::generate(&env),
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
            arbitrator: Address::generate(&env),
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
            arbitrator: Address::generate(&env),
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
