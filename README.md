# StellArts 🌟

![StellArts Logo](./Stellarts.png)

> **Uber for Artisans — Built on Stellar**

StellArts is a decentralized, location-based marketplace that connects skilled artisans with nearby clients. We combine **fast discovery**, **trusted engagement**, and **secure payments** powered by the **Stellar blockchain** to create a transparent platform for local services.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Stellar](https://img.shields.io/badge/Stellar-Soroban-blue)](https://stellar.org/soroban)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-13.5.1-black)](https://nextjs.org/)

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Core Features](#-core-features)
- [Getting Started](#-getting-started)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Smart Contracts](#-smart-contracts)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🚀 Overview

In many regions, finding reliable artisans (plumbers, electricians, carpenters) relies heavily on word-of-mouth, leading to limited visibility for workers and lack of trust for clients.

**StellArts** solves this by offering:
- **For Clients**: Easy discovery of verified artisans, transparent reviews, and secure escrow payments.
- **For Artisans**: Broader market access, fair compensation, and a reputation system that they own.

Our vision is to become the trusted decentralized infrastructure for the gig economy, promoting financial inclusion through Stellar's low-cost, high-speed network.

---

## 🛠️ Core Features

### 🔎 Discovery & Matching
- **Geolocation-Based**: Uber-like proximity matching to find the nearest available artisan.
- **Rich Profiles**: Verified skills, work history, and real-time availability.

### 💳 Secure & Efficient Payments
- **Escrow Smart Contracts**: Funds are locked exclusively until job completion is confirmed, eliminating fraud.
- **Stellar-Powered**: 
    - **Low Fees**: Transactions cost < $0.01 (micropayment friendly).
    - **Fast Settlement**: Payments settle in 3-5 seconds.
    - **Multi-Currency**: Support for USDC and local assets.

### ⭐ Trust & Reputation
- **Transparent Reviews**: Rating system designed to be tamper-resistant.
- **Owned Reputation**: Future plans for on-chain reputation storage.

---

## 🚀 Getting Started

Follow these steps to set up the development environment.

### Prerequisites
- **Docker & Docker Compose** (for Backend)
- **Node.js 18+** (for Frontend)
- **Rust & Soroban CLI** (for Smart Contracts)

### Backend (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Set up environment variables:
   ```bash
   cp env.example .env
   # Edit .env with your configuration if needed
   ```
3. Start the services:
   ```bash
   make up
   # Or: docker-compose up -d
   ```
   The API will be available at `http://localhost:8000`. Interact with the docs at `http://localhost:8000/docs`.

### Frontend (Next.js)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

### Smart Contracts (Soroban)

For detailed contract development, see [contracts/README.md](./contracts/README.md).

```bash
cd contracts
cargo test
```

---

## 📦 Tech Stack

- **Frontend**: Next.js 13 (App Router), TypeScript, Tailwind CSS, Radix UI.
- **Backend**: FastAPI, Python 3.11, SQLAlchemy, PostgreSQL, Redis.
- **Blockchain**: Stellar Network, Soroban Smart Contracts (Rust).
- **Infrastructure**: Docker, GitHub Actions, AWS (planned).

---

## 📁 Project Structure

```
StellArts/
├── frontend/              # Next.js web application
├── backend/               # FastAPI backend & database
│   ├── app/               # Application code
│   └── alembic/           # Database migrations
├── contracts/             # Stellar Soroban smart contracts
│   ├── escrow/            # Payment holding logic
│   └── reputation/        # Review logic
└── README.md              # this file
```

---

## 🔐 Smart Contracts

We use **Soroban** to handle trustless logic:
- **Escrow**: Locks funds and handles release/refunds based on job status.
- **Reputation**: Stores rating hashes and scores to prevent manipulation.

> See [contracts/README.md](./contracts/README.md) for deployment and invocation guides.

---

## 💡 Roadmap

### Phase 1: MVP (Current) ✅
- [x] User auth & Artisan profiles
- [x] Location-based search & Booking
- [x] Stellar payment integration (Testnet)
- [x] Basic Review system

### Phase 2: Smart Contract Hardening 🚧
- [ ] Automated payment release flows
- [ ] Dispute resolution mechanism (Arbitration)
- [ ] Multi-sig wallet support

### Phase 3: Enhanced Platform 🔜
- [ ] On-chain reputation data
- [ ] In-app chat & Push notifications
- [ ] Mobile Apps (iOS/Android)

---

## 🤝 Contributing

We welcome contributions!

1. **Fork** the repo and **Clone** it.
2. Create a **Feature Branch** (`git checkout -b feature/cool-feature`).
3. **Commit** your changes.
4. **Test** your code:
   - Backend: `make test` (inside `/backend`)
   - Frontend: `npm test` (inside `/frontend`)
   - Contracts: `cargo test` (inside `/contracts`)
5. **Push** and open a **Pull Request**.

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) first.

---

## 📄 License & Contact

This project is licensed under the **MIT License**.

- **Website**: [stellarts.io](https://stellarts.io)
- **Twitter**: [@StellArts](https://twitter.com/stellarts)
- **Issues**: [GitHub Issues](https://github.com/yourusername/StellArts/issues)

<p align="center">Made with ❤️ by the StellArts Team</p>
