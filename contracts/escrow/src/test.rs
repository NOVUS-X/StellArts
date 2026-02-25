//! Comprehensive unit test suite for the Escrow contract happy path
//! This module verifies the complete workflow: initialize engagement → mock token → mint tokens → deposit → release
//! Each test step includes assertions on token balances and state transitions
#[cfg(test)]
mod happy_path_tests {
    use crate::{DataKey, Escrow, EscrowContract, EscrowContractClient, Status};
    use soroban_sdk::{token, Address, Env};
    use soroban_sdk::testutils::Address as AddressTestUtils;

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
                self.env.storage()
                    .instance()
                    .get(&DataKey::Escrow(engagement_id))
                    .expect("Escrow should exist")
            })
        }

        /// Initialize an engagement
        fn initialize_engagement(&self, client: &Address, artisan: &Address, amount: i128) -> u64 {
            let deadline = self.env.ledger().timestamp() + 86400;
            self.client_contract.initialize(client, artisan, &amount, &deadline)
        }

        /// Mint tokens to an address
        fn mint_tokens(&self, address: &Address, amount: i128) {
            self.token_contract_client.mint(address, &amount);
        }

        /// Deposit funds into an escrow
        fn deposit_funds(&self, engagement_id: u64) {
            self.client_contract.deposit(&engagement_id, &self.token_address);
        }

        /// Release funds from an escrow
        fn release_funds(&self, engagement_id: u64) {
            self.client_contract.release(&engagement_id, &self.token_address);
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
        assert_eq!(client_balance, initial_mint, "Client should have exactly minted amount");

        let contract_balance = ctx.token_client.balance(&ctx.contract_id);
        assert_eq!(contract_balance, 0, "Contract should have no tokens before deposit");
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
                "Contract holds current engagement amount at iteration {}", i
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
        assert_eq!(escrow.amount, amount);
    }}