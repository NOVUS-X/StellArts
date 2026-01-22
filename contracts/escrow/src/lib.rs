// Escrow contract for StellArts
use soroban_sdk::{contract, contractimpl, contracttype, Address, Env, token};

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Escrow {
    pub client: Address,
    pub artisan: Address,
    pub amount: i128,
    pub status: Status,
    pub deadline: u64,
    pub token: Address,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Status {
    Pending,
    Funded,
    Released,
    Disputed,
    Refunded,
}

#[contracttype]
#[derive(Clone)]
pub enum DataKey {
    Escrow(u64),
}

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowContract {
    // Helper function to setup escrow for testing purposes
    pub fn create_escrow(
        env: Env,
        engagement_id: u64,
        client: Address,
        artisan: Address,
        token: Address,
        amount: i128,
        deadline: u64,
    ) {
        let key = DataKey::Escrow(engagement_id);
        let escrow = Escrow {
            client,
            artisan,
            amount,
            status: Status::Funded,
            deadline,
            token,
        };
        env.storage().persistent().set(&key, &escrow);
    }

    pub fn refund(env: Env, engagement_id: u64) {
        let key = DataKey::Escrow(engagement_id);
        let mut escrow: Escrow = env.storage().persistent().get(&key).unwrap();

        // Logic: Check that env.ledger().timestamp() is greater than escrow.deadline,
        // or verify that the artisan has signed the transaction to indicate mutual cancellation.
        let current_timestamp = env.ledger().timestamp();

        if current_timestamp <= escrow.deadline {
            // If deadline has not passed, artisan must approve (sign)
            escrow.artisan.require_auth();
        }

        // Action: Transfer the escrowed funds from the contract back to the client.
        let token_client = token::Client::new(&env, &escrow.token);
        token_client.transfer(
            &env.current_contract_address(),
            &escrow.client,
            &escrow.amount,
        );

        // State: Update the escrow status to Refunded.
        escrow.status = Status::Refunded;
        env.storage().persistent().set(&key, &escrow);
    }
}

#[cfg(test)]
mod test;
