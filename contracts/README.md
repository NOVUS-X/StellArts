# StellArts Smart Contracts

Soroban smart contracts for the StellArts platform, built on the Stellar blockchain. This repository contains the core logic for escrowed payments and artisan reputation management.

## 📦 Contracts

### 1. Escrow Contract (`escrow`)
Manages secure payment escrow between clients and artisans with multi-stage lifecycle and dispute resolution.
- **Engagement Initialization**: Setup a new service agreement.
- **Fund Escrow**: Client locks funds into the contract.
- **Job Start**: Transition from funded to in-progress (verified by oracle).
- **Fund Release**: Client releases funds to the artisan upon satisfaction.
- **Reclaim**: Client retrieves funds if artisan fails to deliver by a deadline.
- **Dispute Resolution**: Independent arbitrator can resolve conflicts.

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
| 4 | Pay Artisan | `release` | Client |
| - | Raise Conflict | `dispute` | Client/Artisan |
| - | Resolve Conflict | `arbitrate` | Arbitrator |

**Example: Create Engagement**
```bash
stellar contract invoke --id $ESCROW_ID --network testnet --source CLIENT_ACCOUNT -- \
  initialize --client CLIENT_ADDR --artisan ARTISAN_ADDR --amount 1000 --deadline 1713873600
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
