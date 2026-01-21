# StellArts Smart Contracts

Soroban smart contracts for the StellArts platform, built on Stellar blockchain.

## 📦 Contracts

### 1. Escrow Contract
Manages secure payment escrow for artisan bookings:
- **Create Escrow**: Initialize escrow for a new booking
- **Fund Escrow**: Client deposits funds into escrow
- **Complete Job**: Release funds to artisan upon job completion
- **Dispute Job**: Handle disputes between client and artisan
- **Refund Client**: Refund funds to client when necessary

### 2. Reputation Contract
Manages on-chain reputation and reviews for artisans:
- **Init Reputation**: Initialize reputation for new artisans
- **Submit Review**: Clients can submit reviews and ratings
- **Get Reputation**: Retrieve artisan reputation scores
- **Get Review**: Fetch specific review details
- **Has Review**: Check if a review exists for a booking

## 🛠️ Development Setup

### Prerequisites

- **Rust**: 1.75.0 or higher
- **Stellar CLI**: Latest version
- **wasm32-unknown-unknown** target

### Install Prerequisites

```bash
# Install Rust (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Add wasm32 target
rustup target add wasm32-unknown-unknown

# Install Stellar CLI
cargo install --locked stellar-cli --features opt
```

### Build Contracts

```bash
# Build all contracts
cargo build --release --target wasm32-unknown-unknown

# Build specific contract
cd escrow
cargo build --release --target wasm32-unknown-unknown

cd ../reputation
cargo build --release --target wasm32-unknown-unknown
```

### Run Tests

```bash
# Run all tests
cargo test

# Run tests for specific contract
cd escrow
cargo test

cd ../reputation
cargo test

# Run tests with verbose output
cargo test -- --nocapture
```

## 🚀 Deployment

### Deploy to Testnet

```bash
# Deploy escrow contract
stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/escrow.wasm \
  --network testnet \
  --source ACCOUNT_SECRET_KEY

# Deploy reputation contract
stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/reputation.wasm \
  --network testnet \
  --source ACCOUNT_SECRET_KEY
```

### Deploy to Mainnet

```bash
# Deploy escrow contract
stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/escrow.wasm \
  --network mainnet \
  --source ACCOUNT_SECRET_KEY

# Deploy reputation contract
stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/reputation.wasm \
  --network mainnet \
  --source ACCOUNT_SECRET_KEY
```

### Optimize for Production

```bash
# Build with optimizations
cargo build --release --target wasm32-unknown-unknown

# Use stellar-cli to optimize wasm
stellar contract optimize \
  --wasm target/wasm32-unknown-unknown/release/escrow.wasm

stellar contract optimize \
  --wasm target/wasm32-unknown-unknown/release/reputation.wasm
```

## 📖 Contract Interactions

### Escrow Contract

#### Create Escrow
```bash
stellar contract invoke \
  --id CONTRACT_ID \
  --network testnet \
  --source SOURCE_ACCOUNT \
  -- \
  create_escrow \
  --booking_id 1 \
  --client CLIENT_ADDRESS \
  --artisan ARTISAN_ADDRESS \
  --amount 1000
```

#### Fund Escrow
```bash
stellar contract invoke \
  --id CONTRACT_ID \
  --network testnet \
  --source CLIENT_ACCOUNT \
  -- \
  fund_escrow \
  --booking_id 1
```

#### Complete Job
```bash
stellar contract invoke \
  --id CONTRACT_ID \
  --network testnet \
  --source CLIENT_ACCOUNT \
  -- \
  complete_job \
  --booking_id 1
```

### Reputation Contract

#### Initialize Reputation
```bash
stellar contract invoke \
  --id CONTRACT_ID \
  --network testnet \
  --source ARTISAN_ACCOUNT \
  -- \
  init_reputation \
  --artisan ARTISAN_ADDRESS
```

#### Submit Review
```bash
stellar contract invoke \
  --id CONTRACT_ID \
  --network testnet \
  --source CLIENT_ACCOUNT \
  -- \
  submit_review \
  --reviewer CLIENT_ADDRESS \
  --artisan ARTISAN_ADDRESS \
  --booking_id 1 \
  --rating 5 \
  --comment_hash "review_hash"
```

#### Get Reputation
```bash
stellar contract invoke \
  --id CONTRACT_ID \
  --network testnet \
  -- \
  get_reputation \
  --artisan ARTISAN_ADDRESS
```

## 🧪 Testing

### Unit Tests

Each contract includes comprehensive unit tests:

```bash
# Run all tests
cargo test

# Run with coverage
cargo tarpaulin --out Html
```

### Integration Tests

```bash
# Run integration tests
cargo test --test integration_tests
```

## 📝 Contract Architecture

### Escrow Flow

```
1. Client creates booking → Create Escrow
2. Client deposits funds → Fund Escrow
3. Artisan completes job → Job marked complete
4. Client confirms → Complete Job (funds released)
   OR
4. Dispute raised → Dispute Job (admin resolution)
```

### Reputation Flow

```
1. Artisan signs up → Init Reputation
2. Job completed → Client submits review
3. Review stored on-chain → Reputation updated
4. Average rating calculated → Displayed on profile
```

## 🔒 Security Considerations

### Authorization
- All sensitive functions require caller authentication
- Client and artisan addresses are verified for each operation
- Only authorized parties can perform specific actions

### State Management
- Escrow state is immutable once created
- Status transitions follow strict rules
- Reputation data is tamper-resistant

### Best Practices
- Always verify booking IDs match
- Validate rating ranges (1-5)
- Use persistent storage for critical data
- Handle edge cases and errors gracefully

## 🐛 Troubleshooting

### Build Issues

```bash
# Clean and rebuild
cargo clean
cargo build --release --target wasm32-unknown-unknown

# Update dependencies
cargo update
```

### Test Failures

```bash
# Run specific test
cargo test test_name -- --exact

# Show test output
cargo test -- --nocapture
```

### Deployment Issues

```bash
# Check contract size
ls -lh target/wasm32-unknown-unknown/release/*.wasm

# Verify wasm validity
stellar contract inspect --wasm path/to/contract.wasm
```

## 📚 Additional Resources

- [Soroban Documentation](https://soroban.stellar.org/docs)
- [Stellar CLI Guide](https://developers.stellar.org/docs/tools/stellar-cli)
- [Rust Smart Contract Examples](https://github.com/stellar/soroban-examples)
- [Stellar Developer Discord](https://discord.gg/stellardev)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](../LICENSE) file for details.

---

**Note**: These contracts are under active development. Use at your own risk in production environments.
