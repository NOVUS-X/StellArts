#!/bin/bash

# Script to deploy Soroban contracts to local standalone network
# Usage: ./scripts/deploy_local.sh

set -e

echo "🚀 Deploying contracts to local Soroban network..."

# Configuration
RPC_URL="${STELLAR_RPC_URL:-http://localhost:8002/soroban/rpc}"
NETWORK_PASSPHRASE="${STELLAR_NETWORK_PASSPHRASE:-Standalone Network ; September 2022}"
NETWORK="standalone"

# Check if stellar CLI is installed
if ! command -v stellar &> /dev/null; then
    echo "❌ stellar CLI not found. Please install it first:"
    echo "   cargo install --locked stellar-cli"
    exit 1
fi

# Check if the network is running
echo "📡 Checking if local network is available..."
if ! curl -s -X POST "$RPC_URL" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' | grep -q "healthy"; then
    echo "❌ Local Soroban network is not running or not accessible at $RPC_URL"
    echo "   Make sure to run: docker-compose up -d soroban-rpc"
    exit 1
fi

echo "✅ Local network is healthy"

# Generate or use existing identity
echo "🔑 Setting up identity..."
if ! stellar keys ls 2>/dev/null | grep -q "admin"; then
    echo "   Creating admin identity..."
    # Generate a new key for local development
    stellar keys generate admin --network "$NETWORK" --rpc-url "$RPC_URL"
fi

ADMIN_KEY=$(stellar keys address admin)
echo "   Admin key: $ADMIN_KEY"

# Fund the identity from the standalone network's friendbot
echo "💰 Funding admin identity from friendbot..."
FRIENDBOT_URL="http://localhost:8003/friendbot?addr=$ADMIN_KEY"
if curl -s "$FRIENDBOT_URL" | grep -q "success"; then
    echo "✅ Admin identity funded"
else
    echo "⚠️  Friendbot funding may have failed (this is okay if already funded)"
fi

# Deploy Escrow Contract
echo ""
echo "📦 Deploying Escrow contract..."
cd "$(dirname "$0")/../contracts"

ESCROW_WASM="target/wasm32-unknown-unknown/release/escrow.wasm"
if [ ! -f "$ESCROW_WASM" ]; then
    echo "   Building escrow contract..."
    make build
fi

ESCROW_HASH=$(stellar contract install \
    --network "$NETWORK" \
    --rpc-url "$RPC_URL" \
    --source admin \
    --wasm "$ESCROW_WASM")

echo "   Escrow WASM hash: $ESCROW_HASH"

ESCROW_CONTRACT_ID=$(stellar contract deploy \
    --network "$NETWORK" \
    --rpc-url "$RPC_URL" \
    --source admin \
    --wasm-hash "$ESCROW_HASH")

echo "✅ Escrow contract deployed: $ESCROW_CONTRACT_ID"

# Deploy Reputation Contract
echo ""
echo "📦 Deploying Reputation contract..."

REPUTATION_WASM="target/wasm32-unknown-unknown/release/reputation.wasm"
if [ ! -f "$REPUTATION_WASM" ]; then
    echo "   Building reputation contract..."
    make build
fi

REPUTATION_HASH=$(stellar contract install \
    --network "$NETWORK" \
    --rpc-url "$RPC_URL" \
    --source admin \
    --wasm "$REPUTATION_WASM")

echo "   Reputation WASM hash: $REPUTATION_HASH"

REPUTATION_CONTRACT_ID=$(stellar contract deploy \
    --network "$NETWORK" \
    --rpc-url "$RPC_URL" \
    --source admin \
    --wasm-hash "$REPUTATION_HASH")

echo "✅ Reputation contract deployed: $REPUTATION_CONTRACT_ID"

# Update backend .env file
echo ""
echo "📝 Updating backend configuration..."
BACKEND_ENV="$(dirname "$0")/../../backend/.env"

if [ -f "$BACKEND_ENV" ]; then
    # Update existing values
    sed -i "s|STELLAR_RPC_URL=.*|STELLAR_RPC_URL=$RPC_URL|g" "$BACKEND_ENV"
    sed -i "s|ESCROW_CONTRACT_ID=.*|ESCROW_CONTRACT_ID=$ESCROW_CONTRACT_ID|g" "$BACKEND_ENV"
    sed -i "s|REPUTATION_CONTRACT_ID=.*|REPUTATION_CONTRACT_ID=$REPUTATION_CONTRACT_ID|g" "$BACKEND_ENV"
    echo "✅ Updated $BACKEND_ENV"
else
    echo "⚠️  Backend .env file not found at $BACKEND_ENV"
    echo "   Please manually set these values:"
    echo "   ESCROW_CONTRACT_ID=$ESCROW_CONTRACT_ID"
    echo "   REPUTATION_CONTRACT_ID=$REPUTATION_CONTRACT_ID"
fi

# Summary
echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Contract IDs:"
echo "  Escrow:     $ESCROW_CONTRACT_ID"
echo "  Reputation: $REPUTATION_CONTRACT_ID"
echo ""
echo "Next steps:"
echo "  1. Restart your backend to use the new contract IDs"
echo "  2. Update frontend configuration if needed"
echo "  3. Test contract interactions"
