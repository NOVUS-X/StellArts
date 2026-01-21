#!/bin/bash

# Deployment script for StellArts smart contracts

set -e

# Configuration
NETWORK=${1:-testnet}
SOURCE_ACCOUNT=${STELLAR_SOURCE_ACCOUNT}

echo "🚀 Deploying StellArts Smart Contracts to $NETWORK..."
echo ""

# Check if SOURCE_ACCOUNT is set
if [ -z "$SOURCE_ACCOUNT" ]; then
    echo "❌ Error: STELLAR_SOURCE_ACCOUNT environment variable not set"
    echo "Please set it with: export STELLAR_SOURCE_ACCOUNT=your_secret_key"
    exit 1
fi

# Build contracts first
echo "Building contracts..."
cargo build --release --target wasm32-unknown-unknown

# Deploy Escrow Contract
echo ""
echo "Deploying Escrow Contract..."
ESCROW_CONTRACT_ID=$(stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/escrow.wasm \
  --network $NETWORK \
  --source $SOURCE_ACCOUNT)

echo "✅ Escrow Contract deployed: $ESCROW_CONTRACT_ID"

# Deploy Reputation Contract
echo ""
echo "Deploying Reputation Contract..."
REPUTATION_CONTRACT_ID=$(stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/reputation.wasm \
  --network $NETWORK \
  --source $SOURCE_ACCOUNT)

echo "✅ Reputation Contract deployed: $REPUTATION_CONTRACT_ID"

# Save contract IDs
echo ""
echo "Saving contract IDs..."
cat > .contract_ids <<EOF
ESCROW_CONTRACT_ID=$ESCROW_CONTRACT_ID
REPUTATION_CONTRACT_ID=$REPUTATION_CONTRACT_ID
NETWORK=$NETWORK
EOF

echo ""
echo "✅ All contracts deployed successfully!"
echo ""
echo "Contract IDs saved to .contract_ids"
echo ""
echo "Escrow Contract: $ESCROW_CONTRACT_ID"
echo "Reputation Contract: $REPUTATION_CONTRACT_ID"
