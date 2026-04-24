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
        default_arbitrator: Address,
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
            let default_arbitrator = Address::generate(&env);

            let client_contract = EscrowContractClient::new(&env, &contract_id);
            let token_client = token::Client::new(&env, &token_address);
            let token_contract_client = token::StellarAssetClient::new(&env, &token_address);

            TestContext {
                env,
                contract_id,
                token_address,
                default_arbitrator,
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

        /// Initialize an engagement with the default arbitrator and token
        fn initialize_engagement(&self, client: &Address, artisan: &Address, amount: i128) -> u64 {
            self.initialize_engagement_with_arbitrator(
                client,
                artisan,
                &self.default_arbitrator.clone(),
                amount,
            )
        }

        /// Initialize an engagement with a specific arbitrator and the default token
        fn initialize_engagement_with_arbitrator(
            &self,
            client: &Address,
            artisan: &Address,
            arbitrator: &Address,
            amount: i128,
        ) -> u64 {
            let deadline = self.env.ledger().timestamp() + 86400;
            self.client_contract.initialize(
                client,
                artisan,
                arbitrator,
                &self.token_address,
                &amount,
                &deadline,
                &soroban_sdk::vec![&self.env],
                &0u32,
            )
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
        let engagement_id = ctx.client_contract.initialize(
            &client,
            &artisan,
            &ctx.default_arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &soroban_sdk::vec![&ctx.env],
            &0u32,
        );

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
        let amount: i128 = 5000;

        // Setup: Initialize with per-escrow arbitrator, mint, and deposit
        let engagement_id =
            ctx.initialize_engagement_with_arbitrator(&client, &artisan, &arbitrator, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

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
        let amount: i128 = 5000;

        // Setup: Initialize with per-escrow arbitrator, mint, and deposit
        let engagement_id =
            ctx.initialize_engagement_with_arbitrator(&client, &artisan, &arbitrator, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

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
        let amount: i128 = 5000;

        // Setup: Initialize with per-escrow arbitrator, mint, and deposit
        let engagement_id =
            ctx.initialize_engagement_with_arbitrator(&client, &artisan, &arbitrator, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

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

        // Setup: Initialize with per-escrow arbitrator, mint, and deposit
        let engagement_id =
            ctx.initialize_engagement_with_arbitrator(&client, &artisan, &arbitrator, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

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

        // Setup: Initialize with per-escrow arbitrator, mint, and deposit (but don't dispute)
        let engagement_id =
            ctx.initialize_engagement_with_arbitrator(&client, &artisan, &arbitrator, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

        // Arbitrator tries to resolve non-disputed escrow
        ctx.client_contract
            .resolve_dispute(&engagement_id, &amount, &0, &ctx.token_address);
    }

    /// Test 22: Resolve dispute with split distribution (e.g. 60/40)
    #[test]
    fn test_resolve_dispute_split_distribution() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize with per-escrow arbitrator, mint, and deposit
        let engagement_id =
            ctx.initialize_engagement_with_arbitrator(&client, &artisan, &arbitrator, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);
        assert_eq!(ctx.get_escrow(engagement_id).status, Status::Disputed);

        // Record balances before
        let client_balance_before = ctx.token_client.balance(&client);
        let artisan_balance_before = ctx.token_client.balance(&artisan);

        // Arbitrator resolves: 60% to client (3000), 40% to artisan (2000)
        let client_share: i128 = 3000;
        let artisan_share: i128 = 2000;
        ctx.client_contract.resolve_dispute(
            &engagement_id,
            &client_share,
            &artisan_share,
            &ctx.token_address,
        );

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

    /// Test 23: Resolve dispute with negative amount should fail
    #[test]
    #[should_panic(expected = "Distribution amounts must be non-negative")]
    fn test_resolve_dispute_negative_amount_fails() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize with per-escrow arbitrator, mint, and deposit
        let engagement_id =
            ctx.initialize_engagement_with_arbitrator(&client, &artisan, &arbitrator, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

        // Initiate dispute
        ctx.client_contract.dispute(&engagement_id, &client);

        // Try negative client_amount
        ctx.client_contract
            .resolve_dispute(&engagement_id, &(-1000), &6000, &ctx.token_address);
    }

    /// Test 24: Resolve dispute emits correct event with distribution details
    #[test]
    fn test_resolve_dispute_event_emitted() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let amount: i128 = 5000;

        // Setup: Initialize with per-escrow arbitrator, mint, and deposit
        let engagement_id =
            ctx.initialize_engagement_with_arbitrator(&client, &artisan, &arbitrator, amount);
        ctx.mint_tokens(&client, amount);
        ctx.deposit_funds(engagement_id);

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
        assert!(
            found,
            "expected a DisputeResolvedEvent from the escrow contract"
        );
    }

    /// Test 26: Reclaim fails during grace period without mutual approval
    #[test]
    #[should_panic(
        expected = "Grace period has not passed; both parties must approve early reclaim"
    )]
    fn test_reclaim_fails_during_grace_period() {
        let ctx = TestContext::new();
        let (client, artisan) = create_addresses(&ctx.env);
        let amount: i128 = 5000;

        let now = ctx.env.ledger().timestamp();
        let deadline = now + 10;
        let engagement_id = ctx.client_contract.initialize(
            &client,
            &artisan,
            &ctx.default_arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &soroban_sdk::vec![&ctx.env],
            &0u32,
        );

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
        let engagement_id = ctx.client_contract.initialize(
            &client,
            &artisan,
            &ctx.default_arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &soroban_sdk::vec![&ctx.env],
            &0u32,
        );

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
        let engagement_id = ctx.client_contract.initialize(
            &client,
            &artisan,
            &ctx.default_arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &soroban_sdk::vec![&ctx.env],
            &0u32,
        );

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

// ─────────────────────────────────────────────────────────────────────────────
// Issue #217 – TTL snapshot tests using jump_ledgers
// ─────────────────────────────────────────────────────────────────────────────
#[cfg(test)]
mod ttl_snapshot_tests {
    use crate::{DataKey, EscrowContract, EscrowContractClient, Status};
    use soroban_sdk::testutils::{Address as AddressTestUtils, Ledger, LedgerInfo};
    use soroban_sdk::{token, Address, Env};

    const LEDGERS_PER_SECOND: u32 = 1; // 1 ledger ≈ 5 s; we use 1 for simplicity
    const DAY_LEDGERS: u32 = 17_280; // ~1 day at 5 s/ledger
    const ESCROW_TTL: u32 = 1_036_800; // ~60 days

    struct TtlCtx {
        env: Env,
        contract_id: Address,
        token_address: Address,
        client: EscrowContractClient<'static>,
        token_client: token::Client<'static>,
        token_asset_client: token::StellarAssetClient<'static>,
    }

    impl TtlCtx {
        fn new() -> Self {
            let env = Env::default();
            env.mock_all_auths_allowing_non_root_auth();
            let contract_id = env.register_contract(None, EscrowContract);
            let token_admin = Address::generate(&env);
            let token_contract = env.register_stellar_asset_contract_v2(token_admin);
            let token_address = token_contract.address();
            let client = EscrowContractClient::new(&env, &contract_id);
            let token_client = token::Client::new(&env, &token_address);
            let token_asset_client = token::StellarAssetClient::new(&env, &token_address);
            TtlCtx {
                env,
                contract_id,
                token_address,
                client,
                token_client,
                token_asset_client,
            }
        }

        /// Advance the ledger by `ledgers` ledgers, updating both sequence and timestamp.
        fn jump_ledgers(&self, ledgers: u32) {
            let current = self.env.ledger().get();
            self.env.ledger().set(LedgerInfo {
                sequence_number: current.sequence_number + ledgers,
                timestamp: current.timestamp + (ledgers as u64) * 5,
                ..current
            });
        }

        fn initialize_and_fund(&self, amount: i128) -> (u64, Address, Address) {
            let client_addr = Address::generate(&self.env);
            let artisan_addr = Address::generate(&self.env);
            let arbitrator = Address::generate(&self.env);
            let deadline = self.env.ledger().timestamp() + 86400 * 90; // 90 days
            let id = self.client.initialize(
                &client_addr,
                &artisan_addr,
                &arbitrator,
                &self.token_address,
                &amount,
                &deadline,
                &soroban_sdk::vec![&self.env],
                &0u32,
            );
            self.token_asset_client.mint(&client_addr, &amount);
            self.client.deposit(&id, &self.token_address);
            (id, client_addr, artisan_addr)
        }
    }

    /// TTL-1: Record persists after simulating 30+ days of ledger advancement.
    #[test]
    fn test_ttl_record_persists_after_30_days() {
        let ctx = TtlCtx::new();
        let (id, _, _) = ctx.initialize_and_fund(1_000);

        // Advance ~30 days (30 * DAY_LEDGERS)
        ctx.jump_ledgers(30 * DAY_LEDGERS);

        // Escrow record must still be readable
        let escrow: crate::Escrow = ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env
                .storage()
                .persistent()
                .get(&DataKey::Escrow(id))
                .expect("Escrow should still exist after 30 days")
        });
        assert_eq!(escrow.status, Status::Funded);
    }

    /// TTL-2: TTL extends on deposit state transition.
    #[test]
    fn test_ttl_extends_on_deposit() {
        let ctx = TtlCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let deadline = ctx.env.ledger().timestamp() + 86400 * 90;
        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &1_000i128,
            &deadline,
            &soroban_sdk::vec![&ctx.env],
            &0u32,
        );

        // Advance a few days before depositing
        ctx.jump_ledgers(5 * DAY_LEDGERS);

        ctx.token_asset_client.mint(&client_addr, &1_000i128);
        ctx.client.deposit(&id, &ctx.token_address);

        // After deposit the TTL should have been refreshed; advance another 30 days
        ctx.jump_ledgers(30 * DAY_LEDGERS);

        let escrow: crate::Escrow = ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env
                .storage()
                .persistent()
                .get(&DataKey::Escrow(id))
                .expect("Escrow should persist after TTL extension on deposit")
        });
        assert_eq!(escrow.status, Status::Funded);
    }

    /// TTL-3: TTL extends on release state transition.
    #[test]
    fn test_ttl_extends_on_release() {
        let ctx = TtlCtx::new();
        let (id, _, artisan_addr) = ctx.initialize_and_fund(2_000);

        // Advance 10 days, then release
        ctx.jump_ledgers(10 * DAY_LEDGERS);
        ctx.client.release(&id, &ctx.token_address);

        // Advance another 30 days – record should still be readable (Released status)
        ctx.jump_ledgers(30 * DAY_LEDGERS);

        let escrow: crate::Escrow = ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env
                .storage()
                .persistent()
                .get(&DataKey::Escrow(id))
                .expect("Released escrow should persist after TTL extension")
        });
        assert_eq!(escrow.status, Status::Released);
        assert_eq!(ctx.token_client.balance(&artisan_addr), 2_000);
    }

    /// TTL-4: TTL extends on reclaim (Refunded) state transition.
    #[test]
    fn test_ttl_extends_on_reclaim() {
        let ctx = TtlCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let deadline = ctx.env.ledger().timestamp() + 10;
        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &500i128,
            &deadline,
            &soroban_sdk::vec![&ctx.env],
            &0u32,
        );
        ctx.token_asset_client.mint(&client_addr, &500i128);
        ctx.client.deposit(&id, &ctx.token_address);

        // Jump past deadline + grace period
        ctx.jump_ledgers(20 * DAY_LEDGERS);
        ctx.client.reclaim(&id, &ctx.token_address);

        // Advance another 30 days – record should still be readable
        ctx.jump_ledgers(30 * DAY_LEDGERS);

        let escrow: crate::Escrow = ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env
                .storage()
                .persistent()
                .get(&DataKey::Escrow(id))
                .expect("Refunded escrow should persist after TTL extension")
        });
        assert_eq!(escrow.status, Status::Refunded);
    }

    /// TTL-5: TTL extends on dispute state transition.
    #[test]
    fn test_ttl_extends_on_dispute() {
        let ctx = TtlCtx::new();
        let (id, client_addr, _) = ctx.initialize_and_fund(3_000);

        ctx.jump_ledgers(5 * DAY_LEDGERS);
        ctx.client.dispute(&id, &client_addr);

        ctx.jump_ledgers(30 * DAY_LEDGERS);

        let escrow: crate::Escrow = ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env
                .storage()
                .persistent()
                .get(&DataKey::Escrow(id))
                .expect("Disputed escrow should persist after TTL extension")
        });
        assert_eq!(escrow.status, Status::Disputed);
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Issue #211 – Multi-sig support tests
// ─────────────────────────────────────────────────────────────────────────────
#[cfg(test)]
mod multisig_tests {
    use crate::{DataKey, EscrowContract, EscrowContractClient, Status};
    use soroban_sdk::testutils::{Address as AddressTestUtils, Ledger};
    use soroban_sdk::{token, vec, Address, Env};

    struct MsCtx {
        env: Env,
        contract_id: Address,
        token_address: Address,
        client: EscrowContractClient<'static>,
        token_client: token::Client<'static>,
        token_asset_client: token::StellarAssetClient<'static>,
    }

    impl MsCtx {
        fn new() -> Self {
            let env = Env::default();
            env.mock_all_auths_allowing_non_root_auth();
            let contract_id = env.register_contract(None, EscrowContract);
            let token_admin = Address::generate(&env);
            let tc = env.register_stellar_asset_contract_v2(token_admin);
            let token_address = tc.address();
            let client = EscrowContractClient::new(&env, &contract_id);
            let token_client = token::Client::new(&env, &token_address);
            let token_asset_client = token::StellarAssetClient::new(&env, &token_address);
            MsCtx {
                env,
                contract_id,
                token_address,
                client,
                token_client,
                token_asset_client,
            }
        }
    }

    /// MS-1: Single-sig escrow (no multisig) still works as before.
    #[test]
    fn test_single_sig_release_unchanged() {
        let ctx = MsCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let amount = 1_000i128;
        let deadline = ctx.env.ledger().timestamp() + 86400;

        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &vec![&ctx.env],  // empty → no multisig
            &0u32,
        );
        ctx.token_asset_client.mint(&client_addr, &amount);
        ctx.client.deposit(&id, &ctx.token_address);
        ctx.client.release(&id, &ctx.token_address);

        let escrow: crate::Escrow = ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env.storage().persistent().get(&DataKey::Escrow(id)).unwrap()
        });
        assert_eq!(escrow.status, Status::Released);
        assert_eq!(ctx.token_client.balance(&artisan_addr), amount);
    }

    /// MS-2: Multi-sig release succeeds when threshold is met (2-of-2).
    #[test]
    fn test_multisig_release_succeeds_when_threshold_met() {
        let ctx = MsCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let signer1 = Address::generate(&ctx.env);
        let signer2 = Address::generate(&ctx.env);
        let amount = 5_000i128;
        let deadline = ctx.env.ledger().timestamp() + 86400;

        let signers = vec![&ctx.env, signer1.clone(), signer2.clone()];
        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &signers,
            &2u32, // 2-of-2
        );
        ctx.token_asset_client.mint(&client_addr, &amount);
        ctx.client.deposit(&id, &ctx.token_address);

        // Both signers approve
        ctx.client.multisig_approve(&id, &signer1);
        ctx.client.multisig_approve(&id, &signer2);

        // Release should now succeed
        ctx.client.release(&id, &ctx.token_address);

        let escrow: crate::Escrow = ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env.storage().persistent().get(&DataKey::Escrow(id)).unwrap()
        });
        assert_eq!(escrow.status, Status::Released);
        assert_eq!(ctx.token_client.balance(&artisan_addr), amount);
    }

    /// MS-3: Release fails when multi-sig threshold is not yet met.
    #[test]
    #[should_panic(expected = "Multi-sig threshold not met")]
    fn test_multisig_release_fails_without_approvals() {
        let ctx = MsCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let signer1 = Address::generate(&ctx.env);
        let signer2 = Address::generate(&ctx.env);
        let amount = 5_000i128;
        let deadline = ctx.env.ledger().timestamp() + 86400;

        let signers = vec![&ctx.env, signer1.clone(), signer2.clone()];
        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &signers,
            &2u32,
        );
        ctx.token_asset_client.mint(&client_addr, &amount);
        ctx.client.deposit(&id, &ctx.token_address);

        // Only one signer approves – threshold not met
        ctx.client.multisig_approve(&id, &signer1);

        // Should panic
        ctx.client.release(&id, &ctx.token_address);
    }

    /// MS-4: 1-of-2 threshold – release succeeds after only one approval.
    #[test]
    fn test_multisig_1_of_2_threshold() {
        let ctx = MsCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let signer1 = Address::generate(&ctx.env);
        let signer2 = Address::generate(&ctx.env);
        let amount = 2_000i128;
        let deadline = ctx.env.ledger().timestamp() + 86400;

        let signers = vec![&ctx.env, signer1.clone(), signer2.clone()];
        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &signers,
            &1u32, // 1-of-2
        );
        ctx.token_asset_client.mint(&client_addr, &amount);
        ctx.client.deposit(&id, &ctx.token_address);

        // Only signer1 approves
        ctx.client.multisig_approve(&id, &signer1);
        ctx.client.release(&id, &ctx.token_address);

        assert_eq!(ctx.token_client.balance(&artisan_addr), amount);
    }

    /// MS-5: Unauthorized signer cannot approve.
    #[test]
    #[should_panic(expected = "Signer is not in the multi-sig required signers list")]
    fn test_multisig_unauthorized_signer_rejected() {
        let ctx = MsCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let signer1 = Address::generate(&ctx.env);
        let unauthorized = Address::generate(&ctx.env);
        let amount = 1_000i128;
        let deadline = ctx.env.ledger().timestamp() + 86400;

        let signers = vec![&ctx.env, signer1.clone()];
        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &signers,
            &1u32,
        );
        ctx.token_asset_client.mint(&client_addr, &amount);
        ctx.client.deposit(&id, &ctx.token_address);

        // Unauthorized address tries to approve
        ctx.client.multisig_approve(&id, &unauthorized);
    }

    /// MS-6: Same signer cannot approve twice.
    #[test]
    #[should_panic(expected = "Signer has already approved this escrow")]
    fn test_multisig_duplicate_approval_rejected() {
        let ctx = MsCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let signer1 = Address::generate(&ctx.env);
        let amount = 1_000i128;
        let deadline = ctx.env.ledger().timestamp() + 86400;

        let signers = vec![&ctx.env, signer1.clone()];
        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &signers,
            &1u32,
        );
        ctx.token_asset_client.mint(&client_addr, &amount);
        ctx.client.deposit(&id, &ctx.token_address);

        ctx.client.multisig_approve(&id, &signer1);
        ctx.client.multisig_approve(&id, &signer1); // duplicate – should panic
    }

    /// MS-7: Invalid threshold (0) is rejected at initialization.
    #[test]
    #[should_panic(expected = "multisig_threshold must be between 1 and the number of signers")]
    fn test_multisig_zero_threshold_rejected() {
        let ctx = MsCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let signer1 = Address::generate(&ctx.env);
        let deadline = ctx.env.ledger().timestamp() + 86400;

        let signers = vec![&ctx.env, signer1.clone()];
        ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &1_000i128,
            &deadline,
            &signers,
            &0u32, // invalid
        );
    }

    /// MS-8: Threshold exceeding signer count is rejected.
    #[test]
    #[should_panic(expected = "multisig_threshold must be between 1 and the number of signers")]
    fn test_multisig_threshold_exceeds_signers_rejected() {
        let ctx = MsCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let signer1 = Address::generate(&ctx.env);
        let deadline = ctx.env.ledger().timestamp() + 86400;

        let signers = vec![&ctx.env, signer1.clone()]; // 1 signer
        ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &1_000i128,
            &deadline,
            &signers,
            &3u32, // threshold > signers count
        );
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Issue #212 – cleanup_expired tests
// ─────────────────────────────────────────────────────────────────────────────
#[cfg(test)]
mod cleanup_tests {
    use crate::{DataKey, EscrowContract, EscrowContractClient, Status};
    use soroban_sdk::testutils::{Address as AddressTestUtils, Ledger};
    use soroban_sdk::{token, vec, Address, Env, Vec};

    struct CleanCtx {
        env: Env,
        contract_id: Address,
        token_address: Address,
        client: EscrowContractClient<'static>,
        token_client: token::Client<'static>,
        token_asset_client: token::StellarAssetClient<'static>,
    }

    impl CleanCtx {
        fn new() -> Self {
            let env = Env::default();
            env.mock_all_auths_allowing_non_root_auth();
            let contract_id = env.register_contract(None, EscrowContract);
            let token_admin = Address::generate(&env);
            let tc = env.register_stellar_asset_contract_v2(token_admin);
            let token_address = tc.address();
            let client = EscrowContractClient::new(&env, &contract_id);
            let token_client = token::Client::new(&env, &token_address);
            let token_asset_client = token::StellarAssetClient::new(&env, &token_address);
            CleanCtx {
                env,
                contract_id,
                token_address,
                client,
                token_client,
                token_asset_client,
            }
        }

        fn create_released_escrow(&self) -> (u64, Address) {
            let client_addr = Address::generate(&self.env);
            let artisan_addr = Address::generate(&self.env);
            let arbitrator = Address::generate(&self.env);
            let amount = 1_000i128;
            let deadline = self.env.ledger().timestamp() + 86400;
            let id = self.client.initialize(
                &client_addr,
                &artisan_addr,
                &arbitrator,
                &self.token_address,
                &amount,
                &deadline,
                &vec![&self.env],
                &0u32,
            );
            self.token_asset_client.mint(&client_addr, &amount);
            self.client.deposit(&id, &self.token_address);
            self.client.release(&id, &self.token_address);
            (id, client_addr)
        }

        fn create_refunded_escrow(&self) -> (u64, Address) {
            let client_addr = Address::generate(&self.env);
            let artisan_addr = Address::generate(&self.env);
            let arbitrator = Address::generate(&self.env);
            let amount = 500i128;
            let deadline = self.env.ledger().timestamp() + 10;
            let id = self.client.initialize(
                &client_addr,
                &artisan_addr,
                &arbitrator,
                &self.token_address,
                &amount,
                &deadline,
                &vec![&self.env],
                &0u32,
            );
            self.token_asset_client.mint(&client_addr, &amount);
            self.client.deposit(&id, &self.token_address);
            // Jump past deadline + grace period
            let current = self.env.ledger().get();
            self.env.ledger().set(soroban_sdk::testutils::LedgerInfo {
                timestamp: deadline + 86400 + 1,
                ..current
            });
            self.client.reclaim(&id, &self.token_address);
            (id, client_addr)
        }
    }

    /// CL-1: cleanup_expired removes a Released escrow from storage.
    #[test]
    fn test_cleanup_removes_released_escrow() {
        let ctx = CleanCtx::new();
        let (id, client_addr) = ctx.create_released_escrow();

        // Verify it exists
        assert!(ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env.storage().persistent().has(&DataKey::Escrow(id))
        }));

        let ids: Vec<u64> = vec![&ctx.env, id];
        ctx.client.cleanup_expired(&ids);

        // Verify it was removed
        assert!(!ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env.storage().persistent().has(&DataKey::Escrow(id))
        }));
    }

    /// CL-2: cleanup_expired removes a Refunded escrow from storage.
    #[test]
    fn test_cleanup_removes_refunded_escrow() {
        let ctx = CleanCtx::new();
        let (id, _) = ctx.create_refunded_escrow();

        assert!(ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env.storage().persistent().has(&DataKey::Escrow(id))
        }));

        let ids: Vec<u64> = vec![&ctx.env, id];
        ctx.client.cleanup_expired(&ids);

        assert!(!ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env.storage().persistent().has(&DataKey::Escrow(id))
        }));
    }

    /// CL-3: cleanup_expired emits a cleanup event for each removed escrow.
    #[test]
    fn test_cleanup_emits_event() {
        let ctx = CleanCtx::new();
        let (id, _) = ctx.create_released_escrow();

        let ids: Vec<u64> = vec![&ctx.env, id];
        ctx.client.cleanup_expired(&ids);

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
        assert!(found, "expected a cleanup event from the escrow contract");
    }

    /// CL-4: cleanup_expired on a Funded escrow panics.
    #[test]
    #[should_panic(expected = "is not in a finalized state")]
    fn test_cleanup_funded_escrow_panics() {
        let ctx = CleanCtx::new();
        let client_addr = Address::generate(&ctx.env);
        let artisan_addr = Address::generate(&ctx.env);
        let arbitrator = Address::generate(&ctx.env);
        let amount = 1_000i128;
        let deadline = ctx.env.ledger().timestamp() + 86400;
        let id = ctx.client.initialize(
            &client_addr,
            &artisan_addr,
            &arbitrator,
            &ctx.token_address,
            &amount,
            &deadline,
            &vec![&ctx.env],
            &0u32,
        );
        ctx.token_asset_client.mint(&client_addr, &amount);
        ctx.client.deposit(&id, &ctx.token_address);

        let ids: Vec<u64> = vec![&ctx.env, id];
        ctx.client.cleanup_expired(&ids);
    }

    /// CL-5: cleanup_expired on multiple finalized escrows in one call.
    #[test]
    fn test_cleanup_multiple_escrows() {
        let ctx = CleanCtx::new();
        let (id1, _) = ctx.create_released_escrow();
        let (id2, _) = ctx.create_refunded_escrow();

        let ids: Vec<u64> = vec![&ctx.env, id1, id2];
        ctx.client.cleanup_expired(&ids);

        assert!(!ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env.storage().persistent().has(&DataKey::Escrow(id1))
        }));
        assert!(!ctx.env.as_contract(&ctx.contract_id, || {
            ctx.env.storage().persistent().has(&DataKey::Escrow(id2))
        }));
    }
}
