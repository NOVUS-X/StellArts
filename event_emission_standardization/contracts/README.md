# StellArts Smart Contracts — Standardized Event Schema & Indexer Guide

This documentation details the standardized event emission architecture across StellArts Soroban smart contracts, specifically designed for seamless consumption by off-chain indexers, FastAPI backend services, and real-time ledger watchers.

---

## 🎯 Architecture & Standardization Goals

1. **Deterministic Topic Hierarchy**:
   All contract events follow a strict 2-level or 3-level topic schema:
   - **Topic 0 (`Symbol`)**: Domain / Contract Namespace (e.g. `"Escrow"`, `"Treasury"`).
   - **Topic 1 (`Symbol`)**: Action / State Transition (e.g. `"Initialized"`, `"Funded"`, `"Released"`, `"Disputed"`).
   - **Topic 2 (`u64` - optional context key)**: Entity Identifier (e.g. `engagement_id`).

2. **Self-Contained Structured Payloads**:
   Every event publishes a strongly-typed `#[contracttype]` struct containing all relevant state attributes, eliminating the need for indexers to make secondary RPC read requests.

3. **RPC Filter Optimization**:
   With standardized topics, backend indexers using Stellar RPC `getEvents` can filter precisely by topics (e.g. `["Escrow", "Funded"]` or `["Escrow", "*"]`).

---

## 📊 Standardized Event Schema Matrix

| Event Name | Domain Topic | Action Topic | Topic 2 (Filter Key) | Payload Struct | Description |
|:---|:---|:---|:---|:---|:---|
| **EngagementInitialized** | `"Escrow"` | `"Initialized"` | `engagement_id: u64` | `EngagementInitializedEvent` | New escrow engagement created |
| **FundsDeposited** | `"Escrow"` | `"Funded"` | `engagement_id: u64` | `FundsDepositedEvent` | Client deposited funds into escrow |
| **MaterialsReleased** | `"Escrow"` | `"MaterialsReleased"` | `engagement_id: u64` | `MaterialsReleasedEvent` | Material funds unlocked for artisan |
| **FundsReleased** | `"Escrow"` | `"Released"` | `engagement_id: u64` | `FundsReleasedEvent` | Final escrow funds released to artisan |
| **MilestoneReleased** | `"Escrow"` | `"MilestoneReleased"` | `engagement_id: u64` | `MilestoneReleasedEvent` | Milestone percentage released |
| **Reclaimed** | `"Escrow"` | `"Reclaimed"` | `engagement_id: u64` | `ReclaimedEvent` | Client reclaimed funds after deadline |
| **DisputeInitiated** | `"Escrow"` | `"Disputed"` | `engagement_id: u64` | `DisputeInitiatedEvent` | Dispute raised by client or artisan |
| **DisputeResolved** | `"Escrow"` | `"Resolved"` | `engagement_id: u64` | `DisputeResolvedEvent` | Dispute resolved with fund split |
| **FeeCollected** | `"Escrow"` | `"FeeCollected"` | `engagement_id: u64` | `FeeCollectedEvent` | Protocol fee transferred to treasury |
| **TreasuryConfigured** | `"Treasury"` | `"Configured"` | _None_ | `TreasuryConfiguredEvent` | Treasury address or fee bps updated |
| **EscrowCleanedUp** | `"Escrow"` | `"CleanedUp"` | `engagement_id: u64` | `EscrowCleanedUpEvent` | Finalized escrow purged from state |

---

## 📐 Payload Type Definitions

### 1. `EngagementInitializedEvent`
```rust
pub struct EngagementInitializedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub arbitrator: Address,
    pub token: Address,
    pub material_amount: i128,
    pub labor_amount: i128,
    pub deadline: u64,
}
```

### 2. `FundsDepositedEvent`
```rust
pub struct FundsDepositedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub token: Address,
    pub amount: i128,
}
```

### 3. `FundsReleasedEvent`
```rust
pub struct FundsReleasedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub amount: i128,
}
```

### 4. `MilestoneReleasedEvent`
```rust
pub struct MilestoneReleasedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub milestone_index: u32,
    pub percentage: u32,
    pub amount: i128,
}
```

### 5. `ReclaimedEvent`
```rust
pub struct ReclaimedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub amount: i128,
    pub timestamp: u64,
}
```

### 6. `DisputeInitiatedEvent`
```rust
pub struct DisputeInitiatedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub amount: i128,
    pub initiator: Address,
    pub timestamp: u64,
}
```

### 7. `DisputeResolvedEvent`
```rust
pub struct DisputeResolvedEvent {
    pub engagement_id: u64,
    pub client: Address,
    pub artisan: Address,
    pub token: Address,
    pub client_amount: i128,
    pub artisan_amount: i128,
    pub resolver: Address,
    pub timestamp: u64,
}
```

### 8. `FeeCollectedEvent`
```rust
pub struct FeeCollectedEvent {
    pub engagement_id: u64,
    pub treasury: Address,
    pub token: Address,
    pub fee_amount: i128,
}
```

---

## 🔍 Stellar RPC `getEvents` Query Example

Backend indexers can query specific topics directly using the Soroban RPC `getEvents` endpoint:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "getEvents",
  "params": {
    "startLedger": 123456,
    "filters": [
      {
        "type": "contract",
        "contractIds": ["CA...ESCROW_CONTRACT_ID"],
        "topics": [
          [
            "AAAADwAAAAVFc2Nyb3cA", // ScVal Symbol "Escrow"
            "AAAADwAAAAZGdW5kZWQA"  // ScVal Symbol "Funded"
          ]
        ]
      }
    ],
    "pagination": {
      "limit": 100
    }
  }
}
```
