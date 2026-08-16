# StellArts: Comprehensive QA, Security, and Stability Audit Report
**Date:** August 2026
**Scope:** Smart Contracts (Soroban), Backend (FastAPI), Frontend (Next.js)

---

## 1. Security Vulnerabilities

### 1.1 High Severity: Unauthenticated Reputation Manipulation
**Component:** `contracts/reputation/src/lib.rs` (Soroban Smart Contract)
**Description:** The `rate_artisan` function does not enforce authentication or verify that the caller actually engaged with the artisan. Anyone can spam the contract with 1-star or 5-star reviews, completely undermining the integrity of the platform.
**Recommendation:** Implement cross-contract verification. The Reputation contract must query the Escrow contract to verify that the caller was the `client` in a successfully `Released` or `Refunded` engagement before accepting a rating. Add `client.require_auth()`.

### 1.2 High Severity: Custodial Escrow MVP Risk
**Component:** `backend/app/services/payments.py`
**Description:** The current Phase 1 implementation of the escrow relies on "Classic Stellar Payments" (transferring XLM to a centralized `ESCROW_PUBLIC` wallet) rather than a decentralized Soroban smart contract. This means the platform has full custody of user funds. 
**Recommendation:** Accelerate the integration of the Phase 2 Soroban Escrow smart contract (`contracts/escrow`) into the FastAPI backend so that funds are locked trustlessly on-chain without the server holding custody.

### 1.3 Resolved Security: API Access Control
**Component:** `backend/app/api/v1/endpoints/payments.py`
**Description:** Previously, the `/release` and `/refund` endpoints lacked access control, allowing anyone with a `booking_id` to release funds. 
**Status:** **Resolved**. This was patched during the current development sprint by adding `Depends(require_client)` and validating `booking.client.user_id == current_user.id`.

---

## 2. Stability & Infrastructure Risks

### 2.1 Critical: Missing Blockchain Event Watcher
**Component:** Backend Architecture
**Description:** The backend currently submits transactions via the Stellar SDK and waits for synchronous HTTP responses to update the PostgreSQL database. If the Horizon API times out (HTTP 504) but the transaction succeeds on the blockchain, the database will fail to update, causing a critical desync between the database and the ledger (e.g., funds are gone, but the DB says "Pending").
**Recommendation:** Implement an asynchronous background worker (e.g., Celery or `asyncio`) that polls the Soroban RPC `getEvents` endpoint to listen for `FundsDepositedEvent` and `FundsReleasedEvent`, updating the database idempotently.

### 2.2 Medium: Strict Static Typing Failure (Mypy)
**Component:** CI/CD & `backend/app/`
**Description:** A recent run of the `mypy` strict type-checker resulted in 147 errors across 25 files. The Python backend suffers from missing library stubs (`pydantic_settings`, `aiohttp`) and incorrect SQLAlchemy type mappings.
**Recommendation:** `mypy` has been removed from the CI pipeline to unblock deployments. A dedicated tech-debt sprint is required to refactor the SQLAlchemy models and install type stubs before re-enabling `mypy`.

### 2.3 Medium: Frontend Dependency Instability on Windows
**Component:** `frontend/package.json`
**Description:** The frontend fails to build natively on Windows machines due to hardware-wallet C++ binaries in the Trezor/Stellar SDK dependencies failing their post-install scripts.
**Status:** **Mitigated**. A `.npmrc` file with `ignore-scripts=true` was added, but this limits the ability to use legitimate post-install scripts in the future. Consider migrating the frontend to a Dockerized dev-container to ensure OS-agnostic builds.

---

## 3. QA & Feature Gaps

### 3.1 Missing Implementation: Real-Time WebSockets
**Component:** Frontend UI & Backend API
**Description:** The frontend UI tasks specify requirements for "Real-Time Notifications" (bell icons, toast alerts for escrow releases). However, a deep scan of `backend/app` reveals absolutely no WebSocket (or Server-Sent Events) infrastructure. The `NotificationService` is entirely mocked.
**Recommendation:** Build a FastAPI `WebSocket` gateway in `backend/app/api/v1/endpoints/ws.py` backed by a Redis Pub/Sub channel to stream real-time events to the Next.js frontend.

### 3.2 Feature Enhancement: Escrow Protocol Treasury
**Component:** `contracts/escrow/src/lib.rs`
**Description:** The current Soroban escrow contract transfers 100% of the funds to the artisan upon release. There is no mechanism to extract a platform fee.
**Recommendation:** Add a treasury configuration to the contract. Modify the `release()` and `resolve_dispute()` functions to route a configurable percentage (e.g., 2.5%) of the `amount` to a StellArts protocol treasury address.

---

## Conclusion
The StellArts project has a solid architectural foundation (FastAPI, Next.js, Soroban), but requires immediate attention regarding the **Reputation Contract Security** and the implementation of a **Blockchain Event Watcher** to prevent critical state desyncs as it transitions from its MVP to a fully decentralized Phase 2 release.
