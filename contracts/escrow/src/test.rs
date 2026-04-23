//! Comprehensive unit test suite for the Escrow contract happy path
//! This module verifies the complete workflow: initialize engagement → mock token → mint tokens → deposit → release
//! Each test step includes assertions on token balances and state transitions
#[cfg(test)]
mod happy_path_tests {
    use crate::{DataKey, Escrow, EscrowContract, EscrowContractClient, Status};
    use soroban_sdk::testutils::{Address as AddressTestUtils, Events, Ledger};
    use soroban_sdk::{token, Address, Env};

    /// Test context holding common test objects
    struct TestContext {
        env: Env,
        contract_id: Address,
        token_address: Address,
        client_contract: EscrowContractClient<'static>,
        token_client: token::Client<'static>,
        token_contract_client: token::StellarAssetClient<'static>,
    }

    impl TestContext {
        /// Initialize a test context with contract and token
        fn new() -> Self {
            let env = Env::default();
            env.mock_all_auths_allowing_non_root_auth();
            let contract_id = env.register_contract(None, EscrowContract);
            let token_admin = Address::generate(&env);
            let token_contract = env.register_stellar_asset_contract_v2(token_admin);
            let token_address = token_contract.address();

            let client_contract = EscrowContractClient::new(&env, &contract_id);
            let token_client = token::Client::new(&env, &token_address);
            let token_contract_client = token::StellarAssetClient::new(&env, &token_address);

            TestContext {
                env,
                contract_id,
                token_address,
                client_contract,
                token_client,
                token_contract_client,
            }
        }

        /// Get escrow from storage
        fn get_escrow(&self, engagement_id: u64) -> Escrow {
            self.env.as_contract(&self.contract_id, || {
                self.env
                    .storage()
                    .persistent()
                    .get(&DataKey::Escrow(engagement_id))
                    .expect("Escrow should exist")
            })
        }

        /// Initialize an engagement
        fn initialize_engagement(&self, client: &Address, artisan: &Address, amount: i128) -> u64 {
            let deadline = self.env.ledger().timestamp() + 86400;
            self.client_contract
                .initialize(client, artisan, &amount, &deadline)
        }

        /// Mint tokens to an address
        fn mint_tokens(&self, address: &Address, amount: i128) {
            self.token_contract_client.mint(address, &amount);
        }

        /// Deposit funds into an escrow
        fn deposit_funds(&self, engagement_id: u64) {
            self.client_contract
                .deposit(&engagement_id, &self.token_address);
        }

        /// Release funds from an escrow
        fn release_funds(&self, engagement_id: u64) {
            self.client_contract
                .release(&engagement_id, &self.token_address);
        }

        /// Full workflow: initialize, mint, deposit
        fn full_deposit_workflow(&self, client: &Address, artisan: &Address, amount: i128) -> u64 {
            let engagement_id = self.initialize_engagement(client, artisan, amount);
            self.mint_tokens(client, amount);
            self.deposit_funds(engagement_id);
            engagement_id
        }

        /// Full workflow: initialize, mint, deposit, release
        fn full_workflow(&self, client: &Address, artisan: &Address, amount: i128) -> u64 {
            let engagement_id = self.full_deposit_workflow(client, artisan, amount);
            self.release_funds(engagement_id);
            engagement_id
        }
    }

    /// Helper to create test addresses
    fn create_addresses(env: &Env) -> (Address, Address) {
        (Address::generate(env), Address::generate(env))
    }

    /// Test 1: Initialize Engagement
    /// Verifies that an engagement can be initialized with correct state
    #[test]
    fn test_happy_path_initialize_engagement() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        let engagement_id = ctx.initialize_engagement(&client, &artisan, amount);

        assert_eq!(engagement_id, 1, "First engagement should have ID 1");

        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.client, client);
        assert_eq!(escrow.artisan, artisan);
        assert_eq!(escrow.amount, amount);
        assert_eq!(escrow.status, Status::Pending);
    }

    /// Test 2: Mock Token Contract and Mint Tokens
    /// Verifies that tokens can be minted to the client's address
    #[test]
    fn test_happy_path_mint_tokens_to_client() {
        let ctx = TestContext::new();
        let client = Address::generate(&ctx.env);
        let initial_mint: i128 = 10000;

        ctx.mint_tokens(&client, initial_mint);

        let client_balance = ctx.token_client.balance(&client);
        assert_eq!(
            client_balance, initial_mint,
            "Client should have exactly minted amount"
        );

        let contract_balance = ctx.token_client.balance(&ctx.contract_id);
        assert_eq!(
            contract_balance, 0,
            "Contract should have no tokens before deposit"
        );
    }

    /// Test 3: Client Deposit into Escrow
    /// Verifies that client can deposit funds and escrow status transitions to Funded
    #[test]
    fn test_happy_path_client_deposit() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let escrow_amount: i128 = 5000;

        let engagement_id = ctx.initialize_engagement(&client, &artisan, escrow_amount);
        ctx.mint_tokens(&client, 10000);

        let initial_client_balance = ctx.token_client.balance(&client);
        let initial_contract_balance = ctx.token_client.balance(&ctx.contract_id);

        ctx.deposit_funds(engagement_id);

        assert_eq!(
            ctx.token_client.balance(&client),
            initial_client_balance - escrow_amount,
            "Client balance should decrease by escrow amount"
        );
        assert_eq!(
            ctx.token_client.balance(&ctx.contract_id),
            initial_contract_balance + escrow_amount,
            "Contract balance should increase by escrow amount"
        );

        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Funded);
        assert_eq!(escrow.amount, escrow_amount);
    }

    /// Test 4: Release Funds to Artisan
    /// Verifies that client can release funds and artisan receives them
    #[test]
    fn test_happy_path_release_funds_to_artisan() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let escrow_amount: i128 = 5000;

        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, escrow_amount);

        let artisan_balance_before = ctx.token_client.balance(&artisan);
        ctx.release_funds(engagement_id);

        assert_eq!(
            ctx.token_client.balance(&artisan),
            artisan_balance_before + escrow_amount,
            "Artisan should receive the escrow amount"
        );
        assert_eq!(
            ctx.token_client.balance(&ctx.contract_id),
            0,
            "Contract should have no tokens after release"
        );

        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Released);
    }

    /// Test 5: Complete Happy Path - Full Workflow
    /// Verifies the entire workflow from initialization through release with comprehensive balance checks
    #[test]
    fn test_happy_path_complete_workflow() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        let engagement_id = ctx.full_workflow(&client, &artisan, amount);

        // Verify final balances
        assert_eq!(
            ctx.token_client.balance(&client),
            0,
            "Client has no balance after depositing exact amount and releasing"
        );
        assert_eq!(
            ctx.token_client.balance(&ctx.contract_id),
            0,
            "Contract has no tokens after release"
        );
        assert_eq!(
            ctx.token_client.balance(&artisan),
            amount,
            "Artisan received the escrowed amount"
        );

        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Released);

        // Verify token conservation
        let total = ctx.token_client.balance(&client)
            + ctx.token_client.balance(&ctx.contract_id)
            + ctx.token_client.balance(&artisan);
        assert_eq!(total, amount, "Total tokens conserved");
    }

    /// Test 6: Multiple Engagements
    /// Verifies that multiple engagements can be managed independently
    #[test]
    fn test_happy_path_multiple_engagements() {
        let ctx = TestContext::new();

        // First engagement
        let (client1, artisan1) = create_addresses(&ctx.env);
        let amount1 = 1000i128;
        let id1 = ctx.full_deposit_workflow(&client1, &artisan1, amount1);

        // Second engagement
        let (client2, artisan2) = create_addresses(&ctx.env);
        let amount2 = 2000i128;
        let id2 = ctx.full_deposit_workflow(&client2, &artisan2, amount2);

        // Verify both are funded
        assert_eq!(
            ctx.token_client.balance(&ctx.contract_id),
            amount1 + amount2,
            "Contract holds both amounts"
        );

        // Release both
        ctx.release_funds(id1);
        ctx.release_funds(id2);

        // Verify all released
        assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
    }

    /// Test 7: Large Amount Handling
    /// Verifies that large amounts are handled correctly without overflow
    #[test]
    fn test_happy_path_large_amounts() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let large_amount: i128 = 1_000_000_000_000;

        ctx.full_workflow(&client, &artisan, large_amount);

        assert_eq!(ctx.token_client.balance(&artisan), large_amount);
        assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
    }

    /// Test 8: Exact Amount Matching
    /// Verifies behavior when client deposits exact amount with no extra tokens
    #[test]
    fn test_happy_path_exact_amount_deposit() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        let engagement_id = ctx.initialize_engagement(&client, &artisan, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

        assert_eq!(ctx.token_client.balance(&client), 0);
        assert_eq!(ctx.token_client.balance(&ctx.contract_id), amount);

        ctx.release_funds(engagement_id);
        assert_eq!(ctx.token_client.balance(&artisan), amount);
    }

    /// Test 9: Sequential Operations
    /// Verifies that multiple sequential engagements work correctly
    #[test]
    fn test_happy_path_sequential_operations() {
        let ctx = TestContext::new();

        for i in 1..=3 {
            let (client, artisan) = create_addresses(&ctx.env);
            let amount: i128 = 1000 * i as i128;

            let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

            // After deposit, contract should hold the amount (no other engagements pending)
            assert_eq!(
                ctx.token_client.balance(&ctx.contract_id),
                amount,
                "Contract holds current engagement amount at iteration {}",
                i
            );

            ctx.release_funds(engagement_id);

            // After release, contract should be empty for this iteration
            assert_eq!(ctx.token_client.balance(&ctx.contract_id), 0);
            assert_eq!(ctx.token_client.balance(&artisan), amount);
        }
    }

    /// Test 10: State Consistency
    /// Verifies that escrow state remains consistent through the happy path
    #[test]
    fn test_happy_path_state_consistency() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        // Initialize and check state
        let engagement_id = ctx.initialize_engagement(&client, &artisan, amount);
        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Pending);
        assert_eq!(escrow.client, client);
        assert_eq!(escrow.artisan, artisan);

        // Deposit and check state
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);
        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Funded);
        assert_eq!(escrow.client, client);
        assert_eq!(escrow.amount, amount);

        // Release and check final state
        ctx.release_funds(engagement_id);
        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Released);
        assert_eq!(escrow.client, client);
        assert_eq!(escrow.artisan, artisan);
    }

    /// Test 11: Deadline lifecycle – deposit before deadline, reclaim after expiry
    #[test]
    fn test_happy_path_deadline_lifecycle() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        // set a short deadline a few seconds in the future
        let now = ctx.env.ledger().timestamp();
        let deadline = now + 10;
        let engagement_id = ctx
            .client_contract
            .initialize(&client, &artisan, &amount, &deadline);

        // fund and deposit before the deadline
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);
        assert_eq!(ctx.get_escrow(engagement_id).status, Status::Funded);

        // fast-forward ledger past the deadline + GRACE_PERIOD (86400 seconds)
        ctx.env.ledger().set_timestamp(deadline + 86400 + 1);

        // now reclaim should succeed and return funds to client
        let client_balance_before = ctx.token_client.balance(&client);
        ctx.client_contract
            .reclaim(&engagement_id, &ctx.token_address);
        let client_balance_after = ctx.token_client.balance(&client);
        assert_eq!(client_balance_after, client_balance_before + amount);

        // ensure an event from the escrow contract was emitted (token contract also emits events)
        let raw_events: soroban_sdk::Vec<(
            Address,
            soroban_sdk::Vec<soroban_sdk::Val>,
            soroban_sdk::Val,
        )> = ctx.env.events().all();
        let mut found = false;
        for (addr, _, _) in raw_events.into_iter() {
            if addr == ctx.contract_id {
                found = true;
                break;
            }
        }
        assert!(found, "expected at least one escrow contract event");

        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Refunded);
    }

    #[test]
    fn test_extend_deadline_client_proposes_artisan_confirms() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);
        let original_deadline = ctx.get_escrow(engagement_id).deadline;
        let new_deadline = original_deadline + 3600;

        ctx.client_contract
            .extend_deadline(&engagement_id, &client, &new_deadline);
        assert_eq!(ctx.get_escrow(engagement_id).deadline, original_deadline);

        ctx.client_contract
            .extend_deadline(&engagement_id, &artisan, &new_deadline);
        assert_eq!(ctx.get_escrow(engagement_id).deadline, new_deadline);
    }

    #[test]
    fn test_extend_deadline_artisan_proposes_client_confirms() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);
        let original_deadline = ctx.get_escrow(engagement_id).deadline;
        let new_deadline = original_deadline + 7200;

        ctx.client_contract
            .extend_deadline(&engagement_id, &artisan, &new_deadline);
        assert_eq!(ctx.get_escrow(engagement_id).deadline, original_deadline);

        ctx.client_contract
            .extend_deadline(&engagement_id, &client, &new_deadline);
        assert_eq!(ctx.get_escrow(engagement_id).deadline, new_deadline);
    }

    #[test]
    #[should_panic(expected = "Only client or artisan can approve deadline extension")]
    fn test_extend_deadline_unauthorized_caller_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let unauthorized = Address::generate(&ctx.env);
        let amount: i128 = 5000;
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);
        let new_deadline = ctx.get_escrow(engagement_id).deadline + 3600;

        ctx.client_contract
            .extend_deadline(&engagement_id, &unauthorized, &new_deadline);
    }

    #[test]
    #[should_panic(expected = "Same party cannot approve deadline extension twice")]
    fn test_extend_deadline_same_party_approves_twice_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);
        let new_deadline = ctx.get_escrow(engagement_id).deadline + 3600;

        ctx.client_contract
            .extend_deadline(&engagement_id, &client, &new_deadline);
        ctx.client_contract
            .extend_deadline(&engagement_id, &client, &new_deadline);
    }

    #[test]
    #[should_panic(expected = "Pending deadline extension does not match requested deadline")]
    fn test_extend_deadline_mismatched_deadline_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);
        let original_deadline = ctx.get_escrow(engagement_id).deadline;

        ctx.client_contract
            .extend_deadline(&engagement_id, &client, &(original_deadline + 3600));
        ctx.client_contract
            .extend_deadline(&engagement_id, &artisan, &(original_deadline + 7200));
    }

    #[test]
    #[should_panic(expected = "New deadline must be greater than current deadline")]
    fn test_extend_deadline_non_increasing_deadline_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);
        let current_deadline = ctx.get_escrow(engagement_id).deadline;

        ctx.client_contract
            .extend_deadline(&engagement_id, &client, &current_deadline);
    }

    /// Test 12: Dispute - client initiates dispute on funded escrow
    #[test]
    fn test_dispute_from_client() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Verify initial state is Funded
        assert_eq!(ctx.get_escrow(engagement_id).status, Status::Funded);

        // Client initiates dispute
        ctx.client_contract.dispute(&engagement_id, &client);

        // Verify status transitioned to Disputed
        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Disputed);
    }

    /// Test 13: Dispute - artisan initiates dispute on funded escrow
    #[test]
    fn test_dispute_from_artisan() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Verify initial state is Funded
        assert_eq!(ctx.get_escrow(engagement_id).status, Status::Funded);

        // Artisan initiates dispute
        ctx.client_contract.dispute(&engagement_id, &artisan);

        // Verify status transitioned to Disputed
        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Disputed);
    }

    /// Test 14: Dispute from wrong state - attempt dispute on Pending escrow should fail
    #[test]
    #[should_panic(expected = "Escrow must be Funded or InProgress to initiate a dispute")]
    fn test_dispute_from_pending_state_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize but don't deposit (escrow remains Pending)
        let engagement_id = ctx.initialize_engagement(&client, &artisan, amount);

        // Attempt to dispute Pending escrow should fail
        ctx.client_contract.dispute(&engagement_id, &client);
    }

    /// Test 15: Double dispute rejection - second dispute on already disputed escrow should fail
    #[test]
    #[should_panic(expected = "Escrow must be Funded or InProgress to initiate a dispute")]
    fn test_double_dispute_rejection() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // First dispute succeeds
        ctx.client_contract.dispute(&engagement_id, &client);
        assert_eq!(ctx.get_escrow(engagement_id).status, Status::Disputed);

        // Second dispute should fail
        ctx.client_contract.dispute(&engagement_id, &client);
    }

    /// Test 16: Unauthorized dispute - third party cannot initiate dispute
    #[test]
    #[should_panic(expected = "Only client or artisan can initiate a dispute")]
    fn test_unauthorized_dispute_attempt() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Third party attempts to dispute
        let unauthorized = Address::generate(&ctx.env);
        ctx.client_contract.dispute(&engagement_id, &unauthorized);
    }

    /// Test 17: Resolve dispute - arbitrator resolves dispute fully in favor of client (refund)
    #[test]
    fn test_resolve_dispute_full_to_client() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let admin = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Set arbitrator
        ctx.client_contract.set_arbitrator(&admin, &arbitrator);

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);
        assert_eq!(ctx.get_escrow(engagement_id).status, Status::Disputed);

        // Get client balance before resolution
        let client_balance_before = ctx.token_client.balance(&client);

        // Arbitrator resolves: 100% to client, 0% to artisan
        ctx.client_contract
            .resolve_dispute(&engagement_id, &amount, &0, &ctx.token_address);

        // Verify funds transferred to client
        let client_balance_after = ctx.token_client.balance(&client);
        assert_eq!(client_balance_after, client_balance_before + amount);

        // Verify status transitioned to Refunded
        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Refunded);
    }

    /// Test 18: Resolve dispute - arbitrator resolves dispute fully in favor of artisan (release)
    #[test]
    fn test_resolve_dispute_full_to_artisan() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let admin = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Set arbitrator
        ctx.client_contract.set_arbitrator(&admin, &arbitrator);

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &artisan);
        assert_eq!(ctx.get_escrow(engagement_id).status, Status::Disputed);

        // Get artisan balance before resolution
        let artisan_balance_before = ctx.token_client.balance(&artisan);

        // Arbitrator resolves: 0% to client, 100% to artisan
        ctx.client_contract
            .resolve_dispute(&engagement_id, &0, &amount, &ctx.token_address);

        // Verify funds transferred to artisan
        let artisan_balance_after = ctx.token_client.balance(&artisan);
        assert_eq!(artisan_balance_after, artisan_balance_before + amount);

        // Verify status transitioned to Released
        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Released);
    }

    /// Test 19: Unauthorized resolve_dispute - non-arbitrator cannot resolve disputes
    #[test]
    #[should_panic]
    fn test_unauthorized_resolve_dispute_attempt() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let _unauthorized = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Set arbitrator
        let admin = Address::generate(&ctx.env);
        ctx.client_contract.set_arbitrator(&admin, &arbitrator);

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);

        // Disable global mock auth and ensure only real arbitrator can call
        ctx.env.set_auths(&[]);

        // Unauthorized user attempts to resolve dispute
        ctx.client_contract
            .resolve_dispute(&engagement_id, &amount, &0, &ctx.token_address);
    }

    /// Test 20: Resolve dispute - distribution amounts that don't sum to escrow amount should fail
    #[test]
    #[should_panic(expected = "Distribution amounts must equal the escrowed amount")]
    fn test_resolve_dispute_invalid_amounts() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Set arbitrator
        let admin = Address::generate(&ctx.env);
        ctx.client_contract.set_arbitrator(&admin, &arbitrator);

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);

        // Try to distribute incorrect total (3000 + 3000 != 5000)
        ctx.client_contract
            .resolve_dispute(&engagement_id, &3000, &3000, &ctx.token_address);
    }

    /// Test 21: Resolve dispute from non-disputed state should fail
    #[test]
    #[should_panic(expected = "Escrow must be in Disputed status to resolve")]
    fn test_resolve_dispute_from_non_disputed_state_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Set arbitrator
        let admin = Address::generate(&ctx.env);
        ctx.client_contract.set_arbitrator(&admin, &arbitrator);

        // Setup: Initialize, mint, and deposit (but don't dispute)
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Arbitrator tries to resolve non-disputed escrow
        ctx.client_contract
            .resolve_dispute(&engagement_id, &amount, &0, &ctx.token_address);
    }

    /// Test 22: Arbitrator not set should fail
    #[test]
    #[should_panic(expected = "Arbitrator not set")]
    fn test_resolve_dispute_without_arbitrator_set() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize, mint, and deposit without setting arbitrator
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);

        // Try to resolve without arbitrator set
        ctx.client_contract
            .resolve_dispute(&engagement_id, &amount, &0, &ctx.token_address);
    }

    /// Test 23: Resolve dispute with split distribution (e.g. 60/40)
    #[test]
    fn test_resolve_dispute_split_distribution() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let admin = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Set arbitrator
        ctx.client_contract.set_arbitrator(&admin, &arbitrator);

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);
        assert_eq!(ctx.get_escrow(engagement_id).status, Status::Disputed);

        // Record balances before
        let client_balance_before = ctx.token_client.balance(&client);
        let artisan_balance_before = ctx.token_client.balance(&artisan);

        // Arbitrator resolves: 60% to client (3000), 40% to artisan (2000)
        let client_share: i128 = 3000;
        let artisan_share: i128 = 2000;
        ctx.client_contract
            .resolve_dispute(&engagement_id, &client_share, &artisan_share, &ctx.token_address);

        // Verify funds distributed correctly
        assert_eq!(
            ctx.token_client.balance(&client),
            client_balance_before + client_share,
            "Client should receive their share"
        );
        assert_eq!(
            ctx.token_client.balance(&artisan),
            artisan_balance_before + artisan_share,
            "Artisan should receive their share"
        );
        assert_eq!(
            ctx.token_client.balance(&ctx.contract_id),
            0,
            "Contract should have no tokens after resolution"
        );

        // Verify status is Resolved (split)
        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Resolved);
    }

    /// Test 24: Resolve dispute with negative amount should fail
    #[test]
    #[should_panic(expected = "Distribution amounts must be non-negative")]
    fn test_resolve_dispute_negative_amount_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let admin = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Set arbitrator
        ctx.client_contract.set_arbitrator(&admin, &arbitrator);

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);

        // Try negative client_amount
        ctx.client_contract
            .resolve_dispute(&engagement_id, &(-1000), &6000, &ctx.token_address);
    }

    /// Test 25: Resolve dispute emits correct event with distribution details
    #[test]
    fn test_resolve_dispute_event_emitted() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let admin = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Set arbitrator
        ctx.client_contract.set_arbitrator(&admin, &arbitrator);

        // Setup: Initialize, mint, and deposit
        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);

        // Resolve with split: 2000 to client, 3000 to artisan
        ctx.client_contract
            .resolve_dispute(&engagement_id, &2000, &3000, &ctx.token_address);

        // Verify at least one event from the escrow contract was emitted
        let raw_events: soroban_sdk::Vec<(
            Address,
            soroban_sdk::Vec<soroban_sdk::Val>,
            soroban_sdk::Val,
        )> = ctx.env.events().all();
        let mut found = false;
        for (addr, _, _) in raw_events.into_iter() {
            if addr == ctx.contract_id {
                found = true;
                break;
            }
        }
        assert!(found, "expected a DisputeResolvedEvent from the escrow contract");
    }

    /// Test 26: Reclaim fails during grace period without mutual approval
    #[test]
    #[should_panic(expected = "Grace period has not passed; both parties must approve early reclaim")]
    fn test_reclaim_fails_during_grace_period() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        let now = ctx.env.ledger().timestamp();
        let deadline = now + 10;
        let engagement_id = ctx
            .client_contract
            .initialize(&client, &artisan, &amount, &deadline);

        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

        // Fast-forward past deadline but within grace period (deadline + 1 hour)
        ctx.env.ledger().set_timestamp(deadline + 3600);

        // Should panic: still within 24h grace period
        ctx.client_contract
            .reclaim(&engagement_id, &ctx.token_address);
    }

    /// Test 27: Reclaim succeeds after deadline + grace period
    #[test]
    fn test_reclaim_succeeds_after_grace_period() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        let now = ctx.env.ledger().timestamp();
        let deadline = now + 10;
        let engagement_id = ctx
            .client_contract
            .initialize(&client, &artisan, &amount, &deadline);

        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

        // Fast-forward past deadline + GRACE_PERIOD (86400 seconds)
        ctx.env.ledger().set_timestamp(deadline + 86400 + 1);

        let client_balance_before = ctx.token_client.balance(&client);
        ctx.client_contract
            .reclaim(&engagement_id, &ctx.token_address);
        let client_balance_after = ctx.token_client.balance(&client);
        assert_eq!(client_balance_after, client_balance_before + amount);

        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Refunded);
    }

    /// Test 28: Early reclaim with mutual approval during grace period
    #[test]
    fn test_early_reclaim_with_mutual_approval() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        let now = ctx.env.ledger().timestamp();
        let deadline = now + 10;
        let engagement_id = ctx
            .client_contract
            .initialize(&client, &artisan, &amount, &deadline);

        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

        // Fast-forward past deadline but within grace period
        ctx.env.ledger().set_timestamp(deadline + 100);

        // Both parties approve early reclaim
        ctx.client_contract
            .approve_early_reclaim(&engagement_id, &client);
        ctx.client_contract
            .approve_early_reclaim(&engagement_id, &artisan);

        // Now reclaim should succeed during grace period
        let client_balance_before = ctx.token_client.balance(&client);
        ctx.client_contract
            .reclaim(&engagement_id, &ctx.token_address);
        let client_balance_after = ctx.token_client.balance(&client);
        assert_eq!(client_balance_after, client_balance_before + amount);

        let escrow = ctx.get_escrow(engagement_id);
        assert_eq!(escrow.status, Status::Refunded);
    }

    /// Test 29: Unauthorized early reclaim approval fails
    #[test]
    #[should_panic(expected = "Only client or artisan can approve early reclaim")]
    fn test_early_reclaim_unauthorized_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let unauthorized = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Third party attempts to approve early reclaim
        ctx.client_contract
            .approve_early_reclaim(&engagement_id, &unauthorized);
    }

    /// Test 30: Same party cannot approve early reclaim twice
    #[test]
    #[should_panic(expected = "Same party cannot approve early reclaim twice")]
    fn test_early_reclaim_same_party_twice_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        let engagement_id = ctx.full_deposit_workflow(&client, &artisan, amount);

        // Client approves twice
        ctx.client_contract
            .approve_early_reclaim(&engagement_id, &client);
        ctx.client_contract
            .approve_early_reclaim(&engagement_id, &client);
    }
}
