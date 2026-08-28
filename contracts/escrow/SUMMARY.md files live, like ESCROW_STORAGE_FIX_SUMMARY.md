# Protocol Fee / Treasury Feature

## Overview

Adds a configurable protocol service fee to the escrow contract's payout flow.
Previously, `release()` sent 100% of escrowed funds directly to the artisan
with no mechanism for the platform to collect revenue. This feature introduces
an admin-configured treasury address and fee rate, and routes the calculated
fee to the treasury on every payout path — with the remainder going to the
artisan as before.

## Issue Addressed

> When `release(env, engagement_id, token)` is called, 100% of funds go to the
> artisan. The platform needs a way to collect a service fee.
>
> **Acceptance Criteria:**
>
> - Add `init_treasury` to configure the StellArts treasury address and
>   `fee_basis_points` (e.g., 250 for 2.5%).
> - Route the calculated fee to the treasury and the remainder to the artisan
>   during `release()`.

## Implementation

**Location:** `contracts/escrow/src/lib.rs`

### 1. Treasury configuration

```rust
pub struct TreasuryConfig {
    pub treasury_address: Address,
    pub fee_basis_points: u32,
}

const MAX_FEE_BPS: u32 = 1_000; // 10% hard cap
```

### 2. `init_treasury` — admin-gated setup

```rust
pub fn init_treasury(env: Env, admin: Address, treasury_address: Address, fee_basis_points: u32)
```

- Only the address registered via `init_admin` can call this.
- Requires `admin.require_auth()`.
- Rejects any `fee_basis_points` above 1000 (10%).
- Stores the config in persistent storage and emits a `TreasuryInitializedEvent`.
- `get_treasury()` reads the current config back (returns `None` if never set).

### 3. Fee routing on every payout path

A shared helper, `pay_artisan_with_optional_fee()`, is called from:

- `release()`
- `release_milestone()`
- `resolve_dispute()` (fee applied only to the artisan's share of a split)
- `resolve_dispute_dao()` (fee split further between treasury and jury reward pool)

Logic:

- If a treasury is configured: calculate the fee, transfer it to the treasury,
  transfer the remainder to the artisan, emit a `FeeCollectedEvent`.
- If no treasury is configured: transfer 100% to the artisan (unchanged legacy
  behavior — fully backward compatible).

### 4. Fee math

```rust
fn calculate_fee(amount: i128, fee_bps: u32) -> i128 {
    amount.checked_mul(fee_bps as i128).expect("fee calculation overflow") / 10_000
}
```

- Floor-rounded, so `fee + artisan_payout == amount` exactly on every payout —
  no dust is ever left behind in the contract.
- Client refunds in dispute resolution are never fee'd — only the artisan's
  share is subject to the fee.

## Testing

**Location:** `contracts/escrow/src/test.rs`, module `fee_tests`

| Test                                                                   | Verifies                                                                    |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `test_init_treasury_sets_config`                                       | Admin can configure and read back the treasury                              |
| `test_init_treasury_unauthorized_fails`                                | Non-admin cannot configure treasury                                         |
| `test_init_treasury_exceeds_max_bps_fails`                             | Fee rate above 10% is rejected                                              |
| `test_release_deducts_fee_exact_math`                                  | Correct split on a clean amount (2.5% of 10,000)                            |
| `test_release_fee_rounding_no_dust`                                    | Floor rounding, fee + payout == original amount                             |
| `test_release_without_treasury_configured_full_amount_to_artisan`      | Legacy behavior preserved when no treasury is set                           |
| `test_resolve_dispute_fee_applied_to_artisan_share_only`               | Fee applies only to artisan's split share                                   |
| `test_resolve_dispute_full_refund_no_fee`                              | Full client refund is never fee'd                                           |
| `test_resolve_dispute_full_release_fee_applied`                        | Full artisan release via dispute still fee'd                                |
| `test_fee_math_no_dust_across_many_amounts`                            | No-dust invariant holds across a range of odd amounts                       |
| `test_release_fee_applies_to_remaining_labor_after_materials_released` | Fee correctly applies to the labor remainder after a materials-only release |

Additional coverage in `dao_dispute_tests` (`DAO-12`–`DAO-17`) verifies fee
splitting between the treasury and the DAO jury reward pool.

### Result

```
cargo test fee_tests

running 11 tests
test test::fee_tests::test_init_treasury_sets_config ... ok
test test::fee_tests::test_resolve_dispute_full_refund_no_fee ... ok
test test::fee_tests::test_release_fee_rounding_no_dust ... ok
test test::fee_tests::test_release_deducts_fee_exact_math ... ok
test test::fee_tests::test_resolve_dispute_full_release_fee_applied ... ok
test test::fee_tests::test_release_fee_applies_to_remaining_labor_after_materials_released ... ok
test test::fee_tests::test_resolve_dispute_fee_applied_to_artisan_share_only ... ok
test test::fee_tests::test_init_treasury_exceeds_max_bps_fails - should panic ... ok
test test::fee_tests::test_init_treasury_unauthorized_fails - should panic ... ok
test test::fee_tests::test_release_without_treasury_configured_full_amount_to_artisan ... ok
test test::fee_tests::test_fee_math_no_dust_across_many_amounts ... ok

test result: ok. 11 passed; 0 failed; 0 ignored; 0 measured; 106 filtered out
```

## Events Emitted

| Event           | Payload                                                   | When                          |
| --------------- | --------------------------------------------------------- | ----------------------------- |
| `treasury_init` | `TreasuryInitializedEvent { treasury, fee_basis_points }` | On `init_treasury`            |
| `fee_collected` | `FeeCollectedEvent { id, treasury, fee_amount, token }`   | On any payout where `fee > 0` |

## Design Notes

- **Backward compatible** — no treasury means no behavior change.
- **10% hard cap** prevents admin misconfiguration.
- **No dust** — floor rounding guarantees the fee and payout always
  reconstruct the original amount exactly.
- **Client protection** — refunds to the client are never subject to the fee,
  even in split dispute resolutions.
