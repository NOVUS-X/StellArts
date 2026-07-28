use crate::{StakingContract, StakingContractClient};
use soroban_sdk::testutils::{Address as AddressTestUtils, Ledger};
use soroban_sdk::{token, Address, Env};

struct TestContext {
    env: Env,
    admin: Address,
    contract: StakingContractClient<'static>,
    token_address: Address,
    token_client: token::Client<'static>,
    token_admin_client: token::StellarAssetClient<'static>,
}

impl TestContext {
    fn new(unbonding_period: u64) -> Self {
        let env = Env::default();
        env.mock_all_auths_allowing_non_root_auth();

        let contract_id = env.register_contract(None, StakingContract);
        let admin = Address::generate(&env);
        let contract = StakingContractClient::new(&env, &contract_id);
        contract.initialize(&admin, &unbonding_period);

        let token_admin = Address::generate(&env);
        let token_contract = env.register_stellar_asset_contract_v2(token_admin);
        let token_address = token_contract.address();
        let token_client = token::Client::new(&env, &token_address);
        let token_admin_client = token::StellarAssetClient::new(&env, &token_address);

        Self {
            env,
            admin,
            contract,
            token_address,
            token_client,
            token_admin_client,
        }
    }

    fn mint(&self, to: &Address, amount: i128) {
        self.token_admin_client.mint(to, &amount);
    }

    fn deposit(&self, user: &Address, amount: i128) {
        self.contract.deposit(user, &self.token_address, &amount);
    }

    fn withdraw(&self, user: &Address, amount: i128) {
        self.contract.withdraw(user, &self.token_address, &amount);
    }

    fn staked(&self, user: &Address) -> i128 {
        self.contract.get_staked_balance(user, &self.token_address)
    }

    fn token_balance(&self, user: &Address) -> i128 {
        self.token_client.balance(user)
    }

    fn advance_time(&self, seconds: u64) {
        self.env.ledger().with_mut(|li| {
            li.timestamp += seconds;
        });
    }
}

#[test]
fn test_deposit_and_get_staked_balance() {
    let ctx = TestContext::new(0);
    let user = Address::generate(&ctx.env);
    ctx.mint(&user, 1_000);

    assert_eq!(ctx.staked(&user), 0);
    ctx.deposit(&user, 400);
    assert_eq!(ctx.staked(&user), 400);
    assert_eq!(ctx.token_balance(&user), 600);

    ctx.deposit(&user, 100);
    assert_eq!(ctx.staked(&user), 500);
}

#[test]
fn test_multiple_users_independent_balances() {
    let ctx = TestContext::new(0);
    let alice = Address::generate(&ctx.env);
    let bob = Address::generate(&ctx.env);
    let carol = Address::generate(&ctx.env);

    ctx.mint(&alice, 1_000);
    ctx.mint(&bob, 2_000);
    ctx.mint(&carol, 500);

    ctx.deposit(&alice, 300);
    ctx.deposit(&bob, 1_500);
    ctx.deposit(&carol, 50);

    assert_eq!(ctx.staked(&alice), 300);
    assert_eq!(ctx.staked(&bob), 1_500);
    assert_eq!(ctx.staked(&carol), 50);

    ctx.withdraw(&bob, 500);
    assert_eq!(ctx.staked(&alice), 300);
    assert_eq!(ctx.staked(&bob), 1_000);
    assert_eq!(ctx.staked(&carol), 50);
    assert_eq!(ctx.token_balance(&bob), 1_000);

    ctx.deposit(&alice, 200);
    assert_eq!(ctx.staked(&alice), 500);
    assert_eq!(ctx.staked(&bob), 1_000);
    assert_eq!(ctx.staked(&carol), 50);
}

#[test]
fn test_multiple_tokens_tracked_separately() {
    let ctx = TestContext::new(0);
    let user = Address::generate(&ctx.env);

    let usdc_admin = Address::generate(&ctx.env);
    let usdc = ctx.env.register_stellar_asset_contract_v2(usdc_admin);
    let usdc_addr = usdc.address();
    let usdc_client = token::Client::new(&ctx.env, &usdc_addr);
    let usdc_admin_client = token::StellarAssetClient::new(&ctx.env, &usdc_addr);

    ctx.mint(&user, 1_000);
    usdc_admin_client.mint(&user, &5_000);

    ctx.contract.deposit(&user, &ctx.token_address, &400);
    ctx.contract.deposit(&user, &usdc_addr, &2_000);

    assert_eq!(
        ctx.contract.get_staked_balance(&user, &ctx.token_address),
        400
    );
    assert_eq!(ctx.contract.get_staked_balance(&user, &usdc_addr), 2_000);
    assert_eq!(ctx.token_balance(&user), 600);
    assert_eq!(usdc_client.balance(&user), 3_000);
}

#[test]
fn test_immediate_withdraw_when_unbonding_is_zero() {
    let ctx = TestContext::new(0);
    let user = Address::generate(&ctx.env);
    ctx.mint(&user, 1_000);

    ctx.deposit(&user, 800);
    ctx.withdraw(&user, 300);

    assert_eq!(ctx.staked(&user), 500);
    assert_eq!(ctx.token_balance(&user), 500);
    assert_eq!(
        ctx.contract
            .get_pending_withdrawal(&user, &ctx.token_address),
        (0, 0)
    );
}

#[test]
fn test_withdraw_respects_unbonding_period() {
    let unbonding = 86_400u64; // 1 day
    let ctx = TestContext::new(unbonding);
    let user = Address::generate(&ctx.env);
    ctx.mint(&user, 1_000);

    ctx.deposit(&user, 1_000);
    ctx.withdraw(&user, 400);

    // Active stake reduced; funds not yet returned.
    assert_eq!(ctx.staked(&user), 600);
    assert_eq!(ctx.token_balance(&user), 0);
    let (pending_amount, unlock_at) = ctx
        .contract
        .get_pending_withdrawal(&user, &ctx.token_address);
    assert_eq!(pending_amount, 400);
    assert_eq!(unlock_at, ctx.env.ledger().timestamp() + unbonding);

    // Too early — should panic (covered in separate test). Advance time then claim.
    ctx.advance_time(unbonding);
    ctx.withdraw(&user, 0); // amount ignored when completing pending

    assert_eq!(ctx.staked(&user), 600);
    assert_eq!(ctx.token_balance(&user), 400);
    assert_eq!(
        ctx.contract
            .get_pending_withdrawal(&user, &ctx.token_address),
        (0, 0)
    );
}

#[test]
#[should_panic(expected = "unbonding period not elapsed")]
fn test_withdraw_before_unbonding_elapses_panics() {
    let ctx = TestContext::new(3_600);
    let user = Address::generate(&ctx.env);
    ctx.mint(&user, 500);

    ctx.deposit(&user, 500);
    ctx.withdraw(&user, 200);
    ctx.advance_time(100);
    ctx.withdraw(&user, 0);
}

#[test]
#[should_panic(expected = "insufficient staked balance")]
fn test_withdraw_more_than_staked_panics() {
    let ctx = TestContext::new(0);
    let user = Address::generate(&ctx.env);
    ctx.mint(&user, 100);
    ctx.deposit(&user, 100);
    ctx.withdraw(&user, 101);
}

#[test]
#[should_panic(expected = "amount must be positive")]
fn test_deposit_zero_panics() {
    let ctx = TestContext::new(0);
    let user = Address::generate(&ctx.env);
    ctx.mint(&user, 100);
    ctx.deposit(&user, 0);
}

#[test]
#[should_panic(expected = "already initialized")]
fn test_double_initialize_panics() {
    let ctx = TestContext::new(0);
    ctx.contract.initialize(&ctx.admin, &10);
}

#[test]
fn test_admin_can_update_unbonding_period() {
    let ctx = TestContext::new(0);
    assert_eq!(ctx.contract.get_unbonding_period(), 0);

    ctx.contract.set_unbonding_period(&1_000);
    assert_eq!(ctx.contract.get_unbonding_period(), 1_000);

    let user = Address::generate(&ctx.env);
    ctx.mint(&user, 100);
    ctx.deposit(&user, 100);
    ctx.withdraw(&user, 50);

    let (amount, unlock_at) = ctx
        .contract
        .get_pending_withdrawal(&user, &ctx.token_address);
    assert_eq!(amount, 50);
    assert_eq!(unlock_at, ctx.env.ledger().timestamp() + 1_000);
    assert_eq!(ctx.token_balance(&user), 0);
}

#[test]
fn test_unknown_user_balance_is_zero() {
    let ctx = TestContext::new(0);
    let stranger = Address::generate(&ctx.env);
    assert_eq!(ctx.staked(&stranger), 0);
}
