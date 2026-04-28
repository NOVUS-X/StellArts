#![no_std]

//! Issue #156 – SOW On-Chain Commitment
//!
//! Changes vs. original escrow contract:
//!   1. `DataKey::ScopeHash(u64)` added to store the IPFS/Arweave CID.
//!   2. `initialize` now requires a non-empty `scope_hash` (Bytes).
//!      Escrows cannot be funded without a valid scope hash.
//!   3. `get_scope_hash` accessor added for off-chain verification.

use soroban_sdk::{
    contract, contractimpl, contracttype, token, vec, Address, Bytes, Env, Symbol, Vec,
};

const ESCROW_TTL: u32 = 1_036_800;
const TTL_THRESHOLD: u32 = 17_280;

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Status {
    Pending,
    Funded,
    Released,
    Refunded,
    Disputed,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Escrow {
    pub client: Address,
    pub artisan: Address,
    pub arbitrator: Address,
    pub token: Address,
    pub amount: i128,
    pub status: Status,
    pub deadline: u64,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DataKey {
    Escrow(u64),
    /// IPFS/Arweave CID of the approved SOW document.
    ScopeHash(u64),
    NextId,
}

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowContract {
    /// Initialize a new escrow engagement.
    ///
    /// `scope_hash` must be a non-empty IPFS/Arweave CID (as raw bytes).
    /// Panics if `scope_hash` is empty – escrows cannot be created without
    /// a committed SOW.
    #[allow(clippy::too_many_arguments)]
    pub fn initialize(
        env: Env,
        client: Address,
        artisan: Address,
        arbitrator: Address,
        token: Address,
        amount: i128,
        deadline: u64,
        scope_hash: Bytes,
    ) -> u64 {
        if client == artisan {
            panic!("client and artisan cannot be the same");
        }
        if arbitrator == client || arbitrator == artisan {
            panic!("arbitrator must be a third party");
        }
        if amount <= 0 {
            panic!("amount must be positive");
        }
        // Issue #156: scope_hash is mandatory
        if scope_hash.is_empty() {
            panic!("scope_hash is required");
        }

        let id_key = DataKey::NextId;
        let id: u64 = env.storage().persistent().get(&id_key).unwrap_or(1);
        env.storage().persistent().set(&id_key, &(id + 1));

        // Store scope hash
        let hash_key = DataKey::ScopeHash(id);
        env.storage().persistent().set(&hash_key, &scope_hash);
        env.storage()
            .persistent()
            .extend_ttl(&hash_key, TTL_THRESHOLD, ESCROW_TTL);

        let escrow = Escrow {
            client: client.clone(),
            artisan: artisan.clone(),
            arbitrator,
            token,
            amount,
            status: Status::Pending,
            deadline,
        };
        let key = DataKey::Escrow(id);
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);

        env.events()
            .publish((Symbol::new(&env, "initialize"), id), (client, artisan, amount));

        id
    }

    /// Deposit funds into escrow. Requires the escrow to have a scope_hash
    /// (enforced at initialize time, so this is always satisfied).
    pub fn deposit(env: Env, engagement_id: u64, token: Address) {
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .unwrap_or_else(|| panic!("escrow not found"));

        if token != escrow.token {
            panic!("token mismatch");
        }
        if env.ledger().timestamp() > escrow.deadline {
            panic!("deadline passed");
        }
        escrow.client.require_auth();
        if escrow.status != Status::Pending {
            panic!("escrow not pending");
        }

        token::Client::new(&env, &token).transfer(
            &escrow.client,
            &env.current_contract_address(),
            &escrow.amount,
        );

        escrow.status = Status::Funded;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);
    }

    /// Release funds to artisan.
    pub fn release(env: Env, engagement_id: u64, token: Address) {
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env
            .storage()
            .persistent()
            .get(&key)
            .expect("escrow not found");

        if token != escrow.token {
            panic!("token mismatch");
        }
        escrow.client.require_auth();
        if env.ledger().timestamp() > escrow.deadline {
            panic!("deadline passed");
        }
        if escrow.status != Status::Funded {
            panic!("escrow not funded");
        }

        token::Client::new(&env, &token).transfer(
            &env.current_contract_address(),
            &escrow.artisan,
            &escrow.amount,
        );

        escrow.status = Status::Released;
        env.storage().persistent().set(&key, &escrow);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, ESCROW_TTL);
    }

    /// Return the stored scope hash for an engagement.
    pub fn get_scope_hash(env: Env, engagement_id: u64) -> Bytes {
        env.storage()
            .persistent()
            .get(&DataKey::ScopeHash(engagement_id))
            .unwrap_or_else(|| panic!("scope hash not found"))
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
#[cfg(test)]
mod tests {
    use super::*;
    use soroban_sdk::testutils::Address as _;
    use soroban_sdk::{Bytes, Env};

    fn fake_hash(env: &Env) -> Bytes {
        Bytes::from_slice(env, b"QmFakeIpfsCid1234567890abcdef")
    }

    fn setup(env: &Env) -> (Address, Address, Address, Address, EscrowContractClient) {
        env.mock_all_auths_allowing_non_root_auth();
        let id = env.register_contract(None, EscrowContract);
        let client = Address::generate(env);
        let artisan = Address::generate(env);
        let arbitrator = Address::generate(env);
        let token_admin = Address::generate(env);
        let tc = env.register_stellar_asset_contract_v2(token_admin);
        (client, artisan, arbitrator, tc.address(), EscrowContractClient::new(env, &id))
    }

    #[test]
    fn test_initialize_with_scope_hash_succeeds() {
        let env = Env::default();
        let (client, artisan, arb, token, contract) = setup(&env);
        let hash = fake_hash(&env);
        let deadline = env.ledger().timestamp() + 86400;

        let id = contract.initialize(&client, &artisan, &arb, &token, &1000i128, &deadline, &hash);
        assert_eq!(id, 1);
        assert_eq!(contract.get_scope_hash(&id), hash);
    }

    #[test]
    #[should_panic(expected = "scope_hash is required")]
    fn test_initialize_without_scope_hash_panics() {
        let env = Env::default();
        let (client, artisan, arb, token, contract) = setup(&env);
        let deadline = env.ledger().timestamp() + 86400;
        contract.initialize(
            &client,
            &artisan,
            &arb,
            &token,
            &1000i128,
            &deadline,
            &Bytes::new(&env), // empty
        );
    }

    #[test]
    fn test_scope_hash_stored_and_retrievable() {
        let env = Env::default();
        let (client, artisan, arb, token, contract) = setup(&env);
        let hash = fake_hash(&env);
        let deadline = env.ledger().timestamp() + 86400;

        let id = contract.initialize(&client, &artisan, &arb, &token, &1000i128, &deadline, &hash);
        let stored = contract.get_scope_hash(&id);
        assert_eq!(stored, hash);
    }

    #[test]
    fn test_full_flow_with_scope_hash() {
        let env = Env::default();
        let (client, artisan, arb, token_addr, contract) = setup(&env);
        let hash = fake_hash(&env);
        let deadline = env.ledger().timestamp() + 86400;
        let amount = 500i128;

        let id =
            contract.initialize(&client, &artisan, &arb, &token_addr, &amount, &deadline, &hash);

        let token_asset = soroban_sdk::token::StellarAssetClient::new(&env, &token_addr);
        token_asset.mint(&client, &amount);

        contract.deposit(&id, &token_addr);
        contract.release(&id, &token_addr);

        let token_client = soroban_sdk::token::Client::new(&env, &token_addr);
        assert_eq!(token_client.balance(&artisan), amount);
    }
}
