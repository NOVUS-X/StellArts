#![no_std]

//! Standalone performance-bond staking contract for StellArts artisans.
//!
//! Artisans can voluntarily lock XLM or USDC (or any SAC-compatible token)
//! into this contract, independent of the Escrow system. Withdrawals respect
//! a configurable unbonding period set at initialization.

use soroban_sdk::{contract, contractimpl, contracttype, token, Address, Env, Symbol};

/// Persistent storage TTL (~60 days) and extension threshold (~1 day).
const STAKE_TTL: u32 = 1_036_800;
const TTL_THRESHOLD: u32 = 17_280;

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DataKey {
    /// Active staked balance for (user, token).
    Balance(Address, Address),
    /// Pending withdrawal for (user, token), if any.
    Pending(Address, Address),
    Admin,
    UnbondingPeriod,
    Initialized,
}

/// Funds that have left the active stake and are waiting out the unbonding period.
#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PendingWithdrawal {
    pub amount: i128,
    pub unlock_at: u64,
}

#[contract]
pub struct StakingContract;

#[contractimpl]
impl StakingContract {
    /// Initialize the staking contract.
    ///
    /// `unbonding_period` is in ledger seconds. A value of `0` allows
    /// immediate withdrawals.
    pub fn initialize(env: Env, admin: Address, unbonding_period: u64) {
        if env.storage().instance().has(&DataKey::Initialized) {
            panic!("already initialized");
        }
        admin.require_auth();

        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage()
            .instance()
            .set(&DataKey::UnbondingPeriod, &unbonding_period);
        env.storage().instance().set(&DataKey::Initialized, &true);
        env.storage()
            .instance()
            .extend_ttl(TTL_THRESHOLD, STAKE_TTL);

        env.events().publish(
            (Symbol::new(&env, "initialize"), admin.clone()),
            unbonding_period,
        );
    }

    /// Lock `amount` of `token` from `user` into the contract as a performance bond.
    pub fn deposit(env: Env, user: Address, token: Address, amount: i128) {
        Self::require_initialized(&env);
        if amount <= 0 {
            panic!("amount must be positive");
        }
        user.require_auth();

        token::Client::new(&env, &token).transfer(&user, &env.current_contract_address(), &amount);

        let key = DataKey::Balance(user.clone(), token.clone());
        let current: i128 = env.storage().persistent().get(&key).unwrap_or(0);
        let new_balance = current
            .checked_add(amount)
            .unwrap_or_else(|| panic!("balance overflow"));
        env.storage().persistent().set(&key, &new_balance);
        env.storage()
            .persistent()
            .extend_ttl(&key, TTL_THRESHOLD, STAKE_TTL);

        env.events().publish(
            (Symbol::new(&env, "deposit"), user, token),
            (amount, new_balance),
        );
    }

    /// Withdraw staked funds.
    ///
    /// - If the unbonding period is `0`, tokens are returned immediately.
    /// - Otherwise the first call moves `amount` into a pending withdrawal that
    ///   unlocks after the unbonding period. A subsequent call with the same
    ///   (or any) amount completes the transfer once `unlock_at` has passed.
    pub fn withdraw(env: Env, user: Address, token: Address, amount: i128) {
        Self::require_initialized(&env);
        user.require_auth();

        let pending_key = DataKey::Pending(user.clone(), token.clone());
        if let Some(pending) = env
            .storage()
            .persistent()
            .get::<_, PendingWithdrawal>(&pending_key)
        {
            Self::complete_pending_withdrawal(&env, &user, &token, &pending_key, &pending);
            return;
        }

        if amount <= 0 {
            panic!("amount must be positive");
        }

        let balance_key = DataKey::Balance(user.clone(), token.clone());
        let current: i128 = env.storage().persistent().get(&balance_key).unwrap_or(0);
        if amount > current {
            panic!("insufficient staked balance");
        }

        let new_balance = current - amount;
        if new_balance == 0 {
            env.storage().persistent().remove(&balance_key);
        } else {
            env.storage().persistent().set(&balance_key, &new_balance);
            env.storage()
                .persistent()
                .extend_ttl(&balance_key, TTL_THRESHOLD, STAKE_TTL);
        }

        let unbonding_period: u64 = env
            .storage()
            .instance()
            .get(&DataKey::UnbondingPeriod)
            .unwrap_or(0);

        if unbonding_period == 0 {
            token::Client::new(&env, &token).transfer(
                &env.current_contract_address(),
                &user,
                &amount,
            );
            env.events()
                .publish((Symbol::new(&env, "withdraw"), user, token), amount);
            return;
        }

        let pending = PendingWithdrawal {
            amount,
            unlock_at: env
                .ledger()
                .timestamp()
                .checked_add(unbonding_period)
                .unwrap_or_else(|| panic!("unlock timestamp overflow")),
        };
        env.storage().persistent().set(&pending_key, &pending);
        env.storage()
            .persistent()
            .extend_ttl(&pending_key, TTL_THRESHOLD, STAKE_TTL);

        env.events().publish(
            (Symbol::new(&env, "unbond_requested"), user, token),
            (pending.amount, pending.unlock_at),
        );
    }

    /// Active (still-bonded) staked balance for `user` in `token`.
    /// Does not include amounts sitting in a pending unbonding withdrawal.
    pub fn get_staked_balance(env: Env, user: Address, token: Address) -> i128 {
        env.storage()
            .persistent()
            .get(&DataKey::Balance(user, token))
            .unwrap_or(0)
    }

    /// Pending withdrawal details, if any. Returns `(amount, unlock_at)` or `(0, 0)`.
    pub fn get_pending_withdrawal(env: Env, user: Address, token: Address) -> (i128, u64) {
        match env
            .storage()
            .persistent()
            .get::<_, PendingWithdrawal>(&DataKey::Pending(user, token))
        {
            Some(p) => (p.amount, p.unlock_at),
            None => (0, 0),
        }
    }

    /// Current unbonding period in seconds.
    pub fn get_unbonding_period(env: Env) -> u64 {
        Self::require_initialized(&env);
        env.storage()
            .instance()
            .get(&DataKey::UnbondingPeriod)
            .unwrap_or(0)
    }

    /// Admin-only update of the unbonding period (applies to future unbond requests).
    pub fn set_unbonding_period(env: Env, unbonding_period: u64) {
        Self::require_initialized(&env);
        let admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .unwrap_or_else(|| panic!("admin not set"));
        admin.require_auth();

        env.storage()
            .instance()
            .set(&DataKey::UnbondingPeriod, &unbonding_period);
        env.storage()
            .instance()
            .extend_ttl(TTL_THRESHOLD, STAKE_TTL);

        env.events().publish(
            (Symbol::new(&env, "set_unbonding_period"), admin),
            unbonding_period,
        );
    }
}

impl StakingContract {
    fn require_initialized(env: &Env) {
        if !env.storage().instance().has(&DataKey::Initialized) {
            panic!("not initialized");
        }
    }

    fn complete_pending_withdrawal(
        env: &Env,
        user: &Address,
        token: &Address,
        pending_key: &DataKey,
        pending: &PendingWithdrawal,
    ) {
        if env.ledger().timestamp() < pending.unlock_at {
            panic!("unbonding period not elapsed");
        }

        env.storage().persistent().remove(pending_key);

        token::Client::new(env, token).transfer(
            &env.current_contract_address(),
            user,
            &pending.amount,
        );

        env.events().publish(
            (Symbol::new(env, "withdraw"), user.clone(), token.clone()),
            pending.amount,
        );
    }
}

#[cfg(test)]
mod test;
