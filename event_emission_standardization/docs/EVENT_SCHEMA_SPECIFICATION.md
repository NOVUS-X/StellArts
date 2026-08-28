# Event Schema Specification for Backend Developers & Indexers

This document provides complete implementation specifications for FastAPI backend services, webhook dispatchers, and external indexers listening to StellArts Soroban smart contract events.

---

## 1. Topic Identification Specification

Soroban events are transmitted with a vector of topics encoded as `ScVal` (XDR). The standardized schema uses:

```
topics[0] = Symbol(Domain)   -> e.g. "Escrow", "Treasury"
topics[1] = Symbol(Action)   -> e.g. "Initialized", "Funded", "Released", "Disputed", "Resolved", "Reclaimed"
topics[2] = U64(EntityId)    -> engagement_id (where applicable)
```

### Topic Matching Rules:
| Domain | Action | Topic Filter Pattern | Description |
|:---|:---|:---|:---|
| `Escrow` | `Initialized` | `["Escrow", "Initialized", *]` | Engagement created in `Pending` state |
| `Escrow` | `Funded` | `["Escrow", "Funded", *]` | Engagement funded by client |
| `Escrow` | `MaterialsReleased` | `["Escrow", "MaterialsReleased", *]` | Material deposit unlocked for artisan |
| `Escrow` | `Released` | `["Escrow", "Released", *]` | Full payout released to artisan |
| `Escrow` | `MilestoneReleased`| `["Escrow", "MilestoneReleased", *]`| Partial milestone paid out |
| `Escrow` | `Reclaimed` | `["Escrow", "Reclaimed", *]` | Escrow refunded to client |
| `Escrow` | `Disputed` | `["Escrow", "Disputed", *]` | Dispute flagged on escrow |
| `Escrow` | `Resolved` | `["Escrow", "Resolved", *]` | Arbitrator/DAO resolution executed |
| `Escrow` | `FeeCollected` | `["Escrow", "FeeCollected", *]` | Fee routed to protocol treasury |
| `Escrow` | `CleanedUp` | `["Escrow", "CleanedUp", *]` | Storage entry purged after finalization |
| `Treasury`| `Configured` | `["Treasury", "Configured"]` | Treasury parameters updated |

---

## 2. Event Payload Schema Mapping

| Action | Status Transition | Backend Database Field Mapping |
|:---|:---|:---|
| `Initialized` | `pending` | `bookings.status = 'pending'`, `bookings.engagement_id = event.engagement_id` |
| `Funded` | `funded` | `bookings.status = 'funded'`, `bookings.amount = event.amount` |
| `MaterialsReleased`| `in_progress` | `bookings.materials_released = true` |
| `Released` | `released` | `bookings.status = 'completed'` / `'released'` |
| `MilestoneReleased`| `in_progress` | `bookings.current_milestone = event.milestone_index + 1` |
| `Reclaimed` | `reclaimed` | `bookings.status = 'cancelled'` / `'reclaimed'` |
| `Disputed` | `disputed` | `bookings.status = 'disputed'`, `bookings.dispute_initiator = event.initiator` |
| `Resolved` | `resolved` | `bookings.status = 'resolved'`, `bookings.client_refund = event.client_amount` |

---

## 3. Python / FastAPI XDR Decoding Guide

Using `stellar-sdk` in Python, decoded event values map directly to standard Python dictionaries:

```python
from stellar_sdk import scval
from stellar_sdk.xdr import SCVal

def decode_scval_topic(topic_xdr_b64: str) -> str | int:
    val = SCVal.from_xdr(topic_xdr_b64)
    return scval.from_scval(val)

def parse_event(raw_event: dict) -> dict:
    topics = [decode_scval_topic(t) for t in raw_event.get("topic", [])]
    domain = topics[0] if len(topics) > 0 else None
    action = topics[1] if len(topics) > 1 else None
    engagement_id = topics[2] if len(topics) > 2 else None
    
    value_scval = SCVal.from_xdr(raw_event.get("value", ""))
    payload = scval.from_scval(value_scval)
    
    return {
        "domain": domain,
        "action": action,
        "engagement_id": engagement_id,
        "payload": payload,
        "ledger": raw_event.get("ledger"),
        "tx_hash": raw_event.get("txHash"),
        "event_id": raw_event.get("id"),
    }
```

---

## 4. Idempotency & Replay Handling

1. **Processed Event Cursor**: Store the latest `processed_event_id` or `ledger_sequence` in `cursor_store`.
2. **Conditional Updates**:
   ```sql
   UPDATE bookings
   SET status = :status, processed_event_id = :event_id, updated_at = NOW()
   WHERE engagement_id = :engagement_id
     AND (processed_event_id IS NULL OR processed_event_id != :event_id);
   ```
3. **Out-of-Order Safety**: Check `ledger_sequence` or verify valid status transitions before applying backward updates.
