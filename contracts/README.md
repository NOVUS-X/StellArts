# StellArts Smart Contracts

Soroban smart contracts for the StellArts platform, built on the Stellar blockchain. This repository contains the core logic for escrowed payments and artisan reputation management.

## 📦 Contracts

### 1. Escrow Contract (`escrow`)
Manages secure payment escrow between clients and artisans with multi-stage lifecycle and dispute resolution.
- **Engagement Initialization**: Setup a new service agreement (optionally with milestone percentages).
- **Fund Escrow**: Client locks funds into the contract.
- **Job Start**: Transition from funded to in-progress (verified by oracle).
- **Fund Release**: Client releases funds to the artisan upon satisfaction (all-or-nothing or per-milestone).
- **Milestone Releases**: For larger jobs, unlock a percentage of funds as each milestone completes.
- **Reclaim**: Client retrieves remaining funds if artisan fails to deliver by a deadline.
- **Dispute Resolution**: Independent arbitrator can resolve conflicts over remaining funds.

### 2. Reputation Contract (`reputation`)
Handles transparent, on-chain scoring for artisans based on completed engagements.
- **Rating Submission**: Clients rate artisans (1-5 stars).
- **Global Stats**: Aggregated average ratings and review counts.
- **Persistent History**: Unalterable reputation record for each artisan.

## 🛠️ Development Setup

### Prerequisites
- **Rust**: 1.75.0+ with `wasm32-unknown-unknown` target.
- **Stellar CLI**: Latest version ([Installation Guide](https://developers.stellar.org/docs/tools/stellar-cli/install)).
- **Account**: A Stellar Testnet account with funds (test with `stellar keys generate --network testnet`).

### Build & Optimize
```bash
# Build all contracts in release mode
cargo build --release --target wasm32-unknown-unknown

# Optimize WASM files for production
stellar contract optimize --wasm target/wasm32-unknown-unknown/release/escrow.wasm
stellar contract optimize --wasm target/wasm32-unknown-unknown/release/reputation.wasm
```

## 🚀 Deployment Process (Testnet)

Follow these steps to deploy and fully initialize the contracts on Testnet.

### 1. Deploy WASM
Deploy the optimized WASM files to get your contract IDs.
```bash
# Deploy Escrow
ESCROW_ID=$(stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/escrow.optimized.wasm \
  --network testnet \
  --source YOUR_ACCOUNT_NAME)

# Deploy Reputation
REPUTATION_ID=$(stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/reputation.optimized.wasm \
  --network testnet \
  --source YOUR_ACCOUNT_NAME)
```

### 2. Initialization
Every contract must be initialized with an **Admin** to enable management and upgrades.

```bash
# Initialize Escrow Admin
stellar contract invoke --id $ESCROW_ID --network testnet --source YOUR_ACCOUNT_NAME -- \
  init_admin --admin YOUR_ACCOUNT_ADDRESS

# Initialize Reputation Admin
stellar contract invoke --id $REPUTATION_ID --network testnet --source YOUR_ACCOUNT_NAME -- \
  init_admin --admin YOUR_ACCOUNT_ADDRESS
```

### 3. Escrow Configuration
The Escrow contract requires an arbitrator and an oracle address to function correctly.

```bash
# Set Arbitrator
stellar contract invoke --id $ESCROW_ID --network testnet --source YOUR_ACCOUNT_NAME -- \
  set_arbitrator --arbitrator ARBITRATOR_ADDRESS

# Set Oracle
stellar contract invoke --id $ESCROW_ID --network testnet --source YOUR_ACCOUNT_NAME -- \
  set_oracle --oracle ORACLE_ADDRESS
```

## 🆙 Upgradeability

StellArts contracts are upgradeable using a delegated pattern. Only the stored **Admin** can perform an upgrade.

### How to Upgrade:
1. **Optimize new WASM**: Build and optimize your new contract version.
2. **Install WASM**: Upload the new WASM byte-code to get a WASM hash.
   ```bash
   WASM_HASH=$(stellar contract install \
     --wasm target/wasm32-unknown-unknown/release/new_version.optimized.wasm \
     --network testnet \
     --source YOUR_ACCOUNT_NAME)
   ```
3. **Execute Upgrade**: Use the old contract ID to point to the new WASM hash.
   ```bash
   stellar contract invoke --id $OLD_CONTRACT_ID --network testnet --source ADMIN_ACCOUNT -- \
     upgrade --new_wasm_hash $WASM_HASH
   ```

## 📖 Contract Interactions

### Escrow Workflow
| Step | Action | Function | Caller |
|:---:|:---|:---|:---|
| 1 | Create Engagement | `initialize` | Application/Client |
| 2 | Lock Funds | `deposit` | Client |
| 3 | Start Work | `start_job` | Oracle |
| 4a | Pay Artisan (all-or-nothing) | `release` | Client |
| 4b | Pay Artisan (per milestone) | `release_milestone` | Client |
| - | Raise Conflict | `dispute` | Client/Artisan |
| - | Resolve Conflict | `resolve_dispute` | Arbitrator |

### Milestone Workflow
For larger artisanal jobs (e.g. renovations), pass milestone percentages at `initialize`. Percentages must be non-zero and sum to **exactly 100** (e.g. `[25, 25, 50]`).

1. `initialize(..., milestones=[25, 25, 50])` — stores ordered milestones; next index starts at `0`.
2. `deposit` — client locks the full `material_amount + labor_amount`.
3. `release_milestone` — client unlocks funds for the **current** milestone only (must proceed in order).
4. Repeat `release_milestone` until the final milestone; status becomes `Released`.
5. Query helpers: `get_milestones`, `get_next_milestone`.

Notes:
- An empty milestone list keeps the legacy all-or-nothing `release` path (and optional `release_materials`).
- Milestone escrows must use `release_milestone` — calling `release` / `release_materials` will fail.
- The last milestone pays any remainder so rounding never leaves dust in the contract.
- `reclaim` / `resolve_dispute` operate on the **remaining** locked balance after partial milestone payouts.

**Example: Create Engagement with Milestones**
```bash
stellar contract invoke --id $ESCROW_ID --network testnet --source CLIENT_ACCOUNT -- \
  initialize \
    --client CLIENT_ADDR \
    --artisan ARTISAN_ADDR \
    --arbitrator ARBITRATOR_ADDR \
    --token TOKEN_ADDR \
    --material_amount 10000 \
    --labor_amount 0 \
    --deadline 1713873600 \
    --multisig_signers '[]' \
    --multisig_threshold 0 \
    --milestones '[25,25,50]'
```

**Example: Release Current Milestone**
```bash
stellar contract invoke --id $ESCROW_ID --network testnet --source CLIENT_ACCOUNT -- \
  release_milestone --engagement_id 1 --token TOKEN_ADDR
```

### Reputation Workflow
**Example: Rate Artisan**
```bash
stellar contract invoke --id $REPUTATION_ID --network testnet --source CLIENT_ACCOUNT -- \
  rate_artisan --artisan ARTISAN_ADDR --stars 5
```

**Example: Get Stats**
```bash
stellar contract invoke --id $REPUTATION_ID --network testnet --source ANYONE -- \
  get_stats --user ARTISAN_ADDR
```

## 🧪 Testing

```bash
# Run all unit tests
cargo test

# Run tests with verbose output
cargo test -- --nocapture
```

---
**Note**: Ensure your `STELLAR_NETWORK_TESTNET` environment variables are correctly configured in your shell for seamless CLI usage.
