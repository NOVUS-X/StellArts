# Payments Integration

This document describes the Stellar-based escrow payment integration for StellArts backend, including payment flows, example API requests/responses, and Stellar account setup for developers.

---

## 1. Overview

The payment system supports three main operations:

1. **Hold** – Move client funds into escrow when a booking is created.
2. **Release** – Release funds to the artisan when the job is confirmed as completed.
3. **Refund** – Refund client if the booking is cancelled or rejected.

All payments are tracked in the `payments` table with a unique transaction ID and mirrored on the Stellar testnet.

---

## 2. Payment Flow Diagrams

### 2.1 Hold Funds

### 2.2 Release Funds

### 2.3 Refund Funds


```mermaid
flowchart TD
    A[Client initiates booking] --> B[POST /payments/hold]
    B --> C[Backend creates payment record & submits to Stellar Testnet]
    C --> D[Funds held in escrow]
    D --> E[Booking confirmed] --> F[POST /payments/release]
    F --> G[Backend submits release to Stellar Testnet]
    G --> H[Funds released to Artisan]

    D --> I[Booking cancelled] --> J[POST /payments/refund]
    J --> K[Backend submits refund to Stellar Testnet]
    K --> L[Funds refunded to Client]



---

## 3. Example API Requests & Responses

### 3.1 Hold Funds
**Request**  
```http
POST /api/v1/payments/hold
Content-Type: application/json

{
  "client_secret": "<CLIENT_SECRET>",
  "booking_id": "<BOOKING_ID>",
  "amount": <AMOUNT>
}
```

**Response**
{
  "status": "success",
  "payment_id": "<PAYMENT_ID>",
  "transaction_hash": "<TRANSACTION_HASH>"
}

### 3.2 Release Funds

**Request**
```
POST /api/v1/payments/release
Content-Type: application/json

{
  "booking_id": "<BOOKING_ID>",
  "artisan_public": "<ARTISAN_PUBLIC_KEY>",
  "amount": <AMOUNT>
}

```
**Response**
```
{
  "status": "success",
  "payment_id": "<PAYMENT_ID>",
  "transaction_hash": "<TRANSACTION_HASH>"
}
```

### 3.3 Refund Funds

**Request**
```

POST /api/v1/payments/refund
Content-Type: application/json

{
  "booking_id": "<BOOKING_ID>",
  "client_public": "<CLIENT_PUBLIC_KEY>",
  "amount": <AMOUNT>
}

```

**Response**
```
{
  "status": "success",
  "payment_id": "<PAYMENT_ID>",
  "transaction_hash": "<TRANSACTION_HASH>"
}
```

## 4. Stellar Testnet Setup for Developers

Create Testnet Account

Use the Stellar Laboratory
 to generate a keypair.

Fund the account using the “Friendbot” faucet.

Set Environment Variables

STELLAR_NETWORK=testnet
STELLAR_SECRET=<secret_key_from_test_account>


Verify Funds

# Use Stellar Laboratory or Stellar SDK to check balance


Test Transactions

All hold, release, and refund operations use the testnet.

Transactions can be verified via Stellar Testnet Explorer
.

## 5. Database Notes

Payments Table

Column	Type	Description
id	UUID	Unique payment ID
booking_id	UUID	Foreign key to bookings
transaction_hash	text	Stellar transaction hash
status	text	held/released/refunded
amount	numeric	Payment amount
from_account	text	Stellar public key of sender
to_account	text	Stellar public key of recipient
memo	text	Transaction memo (e.g., hold-<booking_id>)
created_at	timestamp	Record creation time
updated_at	timestamp	Record last update

## 6. Notes

Always use UUIDs for booking IDs.

Ensure the amount matches the booking amount exactly.

Test all operations on Stellar Testnet before moving to mainnet.

