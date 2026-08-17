# StellArts Smart Contracts

Soroban smart contracts for the StellArts platform, built on the Stellar blockchain. This repository contains the core logic for escrowed payments, artisan reputation management, performance-bond staking, and DAO-based dispute resolution.

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
- **DAO Dispute Resolution (Jury System)**: A registered `DisputeResolution` contract can execute a jury verdict via `resolve_dispute_dao`, splitting the protocol fee between the treasury and a jury reward pool (`set_dispute_resolver` / `set_jury_reward_bps`).

### 2. Reputation Contract (`reputation`)
Handles transparent, on-chain scoring for artisans based on completed engagements.
- **Rating Submission**: Clients rate artisans (1-5 stars).
- **Global Stats**: Aggregated average ratings and review counts.
- **Persistent History**: Unalterable reputation record for each artisan.

### 3. Staking Contract (`staking`)
Voluntary performance-bond staking for artisans (XLM, USDC, or any SAC-compatible token), with an optional unbonding period.

### 4. Dispute Resolution Contract (`dispute_resolution`)
Decentralizes dispute resolution: a jury of exactly **three highly-rated artisans** votes on a disputed escrow, and the majority verdict is executed against the escrow contract.

#### Jury selection
- `create_dispute` registers a disputed escrow (only the client or artisan can register, and only once per engagement).
- `select_jury` receives a candidate pool from the caller (dispute party or admin). Every candidate is verified **on-chain**: the artisan's average rating (from the reputation contract) must be **strictly greater than 4.5** (`total_stars * 2 > review_count * 9`, exact integer math — a rating of exactly 4.5 is rejected), must not be a party to the dispute, and duplicates are dropped.
- Exactly **3 jurors are selected uniformly at random** from the verified pool using the network-provided PRNG (`env.prng()`). The jury is persisted per dispute and **cannot be re-selected once voting begins**.

#### Voting
- Only the three selected jurors may vote (`vote`), and each juror votes **exactly once** — votes are immutable. Verdicts: `FavorClient` (full refund), `FavorArtisan` (full release), or `Split` (50/50).

#### Majority resolution
- `finalize` (callable by any juror, dispute party, or admin) requires **all three jurors to have voted** and resolves by majority (≥ 2 votes for the same verdict).
- A **1-1-1 tie is never silently resolved**: `finalize` fails, the dispute stays open, and the escrow remains `Disputed` so the existing arbitrator fallback path stays available.
- The verdict is executed via the escrow's `resolve_dispute_dao`, which pays the client/artisan shares (with the existing treasury fee rules) and transfers the **jury reward pool** (a configured portion of the protocol fee) back to this contract.

#### Jury rewards
- The reward pool is distributed **only to jurors who voted with the majority**, split exactly (remainder to the first majority juror). Minority/absent jurors receive nothing, rewards are paid exactly once (finalization is atomic and cannot repeat), and the contract can never pay out more than it received.

#### Security & randomness assumptions
- Every state-changing entrypoint enforces authorization (admin for configuration, dispute parties/admin for selection, jurors for votes, jurors/parties/admin for finalization).
- `resolve_dispute_dao` on the escrow contract only accepts calls from the admin-registered resolver contract.
- **Randomness**: Soroban has no secure on-chain randomness. The jury selection uses the network-provided `env.prng()`, seeded from the consensus transaction-set hash — it is **not** cryptographically unpredictable against a corrupt validator, and it is public within a ledger. It is the safest SDK-provided mechanism available on-chain; do not treat it as secret. The caller of `select_jury` supplies the candidate pool, so they can influence *which* eligible artisans are offered, but cannot inject ineligible members (eligibility is verified on-chain) and cannot choose the exact three — the random shuffle does. A future commit-reveal/oracle randomness upgrade can be dropped into `select_jury` without changing the rest of the flow.

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

# Deploy Dispute Resolution
DISPUTE_RESOLUTION_ID=$(stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/dispute_resolution.optimized.wasm \
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

# Initialize Dispute Resolution Admin
stellar contract invoke --id $DISPUTE_RESOLUTION_ID --network testnet --source YOUR_ACCOUNT_NAME -- \
  initialize --admin YOUR_ACCOUNT_ADDRESS

# Point the Dispute Resolution contract at the escrow + reputation contracts
stellar contract invoke --id $DISPUTE_RESOLUTION_ID --network testnet --source YOUR_ACCOUNT_NAME -- \
  set_contracts --admin YOUR_ACCOUNT_ADDRESS \
    --escrow_contract $ESCROW_ID \
    --reputation_contract $REPUTATION_ID

# Register the Dispute Resolution contract as the escrow's DAO resolver and
# configure 50% of the protocol fee as the jury reward pool (5000 bps)
stellar contract invoke --id $ESCROW_ID --network testnet --source YOUR_ACCOUNT_NAME -- \
  set_dispute_resolver --admin YOUR_ACCOUNT_ADDRESS --resolver $DISPUTE_RESOLUTION_ID

stellar contract invoke --id $ESCROW_ID --network testnet --source YOUR_ACCOUNT_NAME -- \
  set_jury_reward_bps --admin YOUR_ACCOUNT_ADDRESS --bps 5000
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
| - | Resolve Conflict (DAO jury) | `resolve_dispute_dao` | DisputeResolution contract |

### Dispute Resolution Workflow (Jury System)
| Step | Action | Function | Caller |
|:---:|:---|:---|:---|
| 1 | Register a disputed escrow | `create_dispute` | Client/Artisan |
| 2 | Select 3 random jurors (rating > 4.5) | `select_jury` | Client/Artisan/Admin |
| 3 | Cast a vote (once per juror) | `vote` | Selected juror |
| 4 | Finalize by majority; distribute rewards | `finalize` | Juror/Party/Admin |

**Example: Register a Dispute and Select a Jury**
```bash
# Register a disputed engagement
stellar contract invoke --id $DISPUTE_RESOLUTION_ID --network testnet --source CLIENT_ACCOUNT -- \
  create_dispute --caller CLIENT_ADDR --engagement_id 1

# Select a jury from a pool of candidate artisan addresses
stellar contract invoke --id $DISPUTE_RESOLUTION_ID --network testnet --source CLIENT_ACCOUNT -- \
  select_jury --caller CLIENT_ADDR --engagement_id 1 \
    --candidates '["ARTISAN_A","ARTISAN_B","ARTISAN_C","ARTISAN_D"]'

# Jurors vote
stellar contract invoke --id $DISPUTE_RESOLUTION_ID --network testnet --source JUROR_ACCOUNT -- \
  vote --juror JUROR_ADDR --engagement_id 1 --verdict FavorArtisan

# Anyone connected to the dispute finalizes it; majority jurors are paid
stellar contract invoke --id $DISPUTE_RESOLUTION_ID --network testnet --source CLIENT_ACCOUNT -- \
  finalize --caller CLIENT_ADDR --engagement_id 1
```

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
