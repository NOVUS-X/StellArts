use soroban_sdk::{contract, contractimpl, contracttype, token, Address, Env};

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Escrow {
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub token: Address,
    pub status: Status,
    pub deadline: u64,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Status {
    Pending,
    Funded,
    Released,
    Disputed,
}

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Escrow(u64),
}

pub trait EscrowTrait {
    fn create_escrow(
        env: Env,
        booking_id: u64,
        client: Address,
        artisan: Address,
        token: Address,
        amount: i128,
        deadline: u64,
    );
    fn fund_escrow(env: Env, booking_id: u64);
    fn release(env: Env, booking_id: u64);
}

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowTrait for EscrowContract {
    fn create_escrow(
        env: Env,
        booking_id: u64,
        client: Address,
        artisan: Address,
        token: Address,
        amount: i128,
        deadline: u64,
    ) {
        let key = DataKey::Escrow(booking_id);
        if env.storage().persistent().has(&key) {
            panic!("Escrow already exists");
        }

        let escrow = Escrow {
            client,
            artisan,
            amount,
            token,
            status: Status::Pending,
            deadline,
        };

        env.storage().persistent().set(&key, &escrow);
    }

    fn fund_escrow(env: Env, booking_id: u64) {
        let key = DataKey::Escrow(booking_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        if escrow.status != Status::Pending {
            panic!("Escrow is not pending");
        }

        escrow.client.require_auth();

        let token_client = token::Client::new(&env, &escrow.token);
        token_client.transfer(&escrow.client, &env.current_contract_address(), &escrow.amount);

        escrow.status = Status::Funded;
        env.storage().persistent().set(&key, &escrow);
    }

    fn release(env: Env, booking_id: u64) {
        let key = DataKey::Escrow(booking_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("Escrow not found");

        // Auth: Require the client’s signature.
        escrow.client.require_auth();

        // Checks: Ensure the escrow status is Funded.
        if escrow.status != Status::Funded {
            panic!("Escrow is not funded");
        }

        // Logic: Transfer the stored escrow amount from the contract address to the artisan’s address.
        let token_client = token::Client::new(&env, &escrow.token);
        token_client.transfer(&env.current_contract_address(), &escrow.artisan, &escrow.amount);

        // State: Update the escrow status to Released.
        escrow.status = Status::Released;
        env.storage().persistent().set(&key, &escrow);
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use soroban_sdk::testutils::Address as _;
    use soroban_sdk::{token, Address, Env, IntoVal};

    fn setup_test(env: &Env) -> (EscrowContractClient<'static>, Address, Address, token::StellarAssetClient<'static>) {
        let contract_id = env.register_contract(None, EscrowContract);
        let client = EscrowContractClient::new(env, &contract_id);

        let client_addr = Address::generate(env);
        let artisan_addr = Address::generate(env);
        let token_admin = Address::generate(env);
        let token_id = env.register_stellar_asset_contract(token_admin);
        let token_client = token::StellarAssetClient::new(env, &token_id);

        (client, client_addr, artisan_addr, token_client)
    }

    #[test]
    fn test_release_funds() {
        let env = Env::default();
        env.mock_all_auths();

        let (client, client_addr, artisan_addr, token_client) = setup_test(&env);
        let amount = 1000;
        let booking_id = 1;

        client.create_escrow(&booking_id, &client_addr, &artisan_addr, &token_client.address, &amount, &100);
        
        token_client.mint(&client_addr, &amount);
        client.fund_escrow(&booking_id);

        assert_eq!(token::Client::new(&env, &token_client.address).balance(&artisan_addr), 0);
        assert_eq!(token::Client::new(&env, &token_client.address).balance(&client.address), amount);

        client.release(&booking_id);

        assert_eq!(token::Client::new(&env, &token_client.address).balance(&artisan_addr), amount);
        assert_eq!(token::Client::new(&env, &token_client.address).balance(&client.address), 0);
    }

    #[test]
    #[should_panic(expected = "Escrow is not funded")]
    fn test_release_unfunded_fails() {
        let env = Env::default();
        env.mock_all_auths();

        let (client, client_addr, artisan_addr, token_client) = setup_test(&env);
        let amount = 1000;
        let booking_id = 1;

        client.create_escrow(&booking_id, &client_addr, &artisan_addr, &token_client.address, &amount, &100);
        
        client.release(&booking_id);
    }

    #[test]
    #[should_panic(expected = "Escrow is not funded")]
    fn test_release_already_released_fails() {
        let env = Env::default();
        env.mock_all_auths();

        let (client, client_addr, artisan_addr, token_client) = setup_test(&env);
        let amount = 1000;
        let booking_id = 1;

        client.create_escrow(&booking_id, &client_addr, &artisan_addr, &token_client.address, &amount, &100);
        token_client.mint(&client_addr, &amount);
        client.fund_escrow(&booking_id);

        client.release(&booking_id);
        client.release(&booking_id);
    }

    #[test]
    #[should_panic] // Should panic due to failed authorization
    fn test_release_not_client_fails() {
        let env = Env::default();
        let (client, client_addr, artisan_addr, token_client) = setup_test(&env);
        let amount = 1000;
        let booking_id = 1;

        env.mock_all_auths();
        client.create_escrow(&booking_id, &client_addr, &artisan_addr, &token_client.address, &amount, &100);
        token_client.mint(&client_addr, &amount);
        client.fund_escrow(&booking_id);

        // Try to release as someone else
        let someone_else = Address::generate(&env);
        env.mock_auths(&[soroban_sdk::testutils::MockAuth {
            address: &someone_else,
            invoke: &soroban_sdk::testutils::MockAuthInvoke {
                contract: &client.address,
                fn_name: "release",
                args: (booking_id,).into_val(&env),
                sub_invokes: &[],
            },
        }]);

        client.release(&booking_id);
    }

    #[test]
    #[should_panic(expected = "Escrow already exists")]
    fn test_create_escrow_already_exists_fails() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, client_addr, artisan_addr, token_client) = setup_test(&env);
        
        client.create_escrow(&1, &client_addr, &artisan_addr, &token_client.address, &1000, &100);
        client.create_escrow(&1, &client_addr, &artisan_addr, &token_client.address, &1000, &100);
    }

    #[test]
    #[should_panic(expected = "Escrow not found")]
    fn test_fund_not_found_fails() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, _, _, _) = setup_test(&env);
        
        client.fund_escrow(&999);
    }

    #[test]
    #[should_panic(expected = "Escrow is not pending")]
    fn test_fund_already_funded_fails() {
        let env = Env::default();
        env.mock_all_auths();
        let (client, client_addr, artisan_addr, token_client) = setup_test(&env);
        
        client.create_escrow(&1, &client_addr, &artisan_addr, &token_client.address, &1000, &100);
        token_client.mint(&client_addr, &1000);
        client.fund_escrow(&1);
        client.fund_escrow(&1);
    }
}
