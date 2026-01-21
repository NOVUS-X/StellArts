#!/bin/bash

# Build script for StellArts smart contracts

set -e

echo "🔨 Building StellArts Smart Contracts..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if wasm32 target is installed
if ! rustup target list | grep -q "wasm32-unknown-unknown (installed)"; then
    echo "Installing wasm32-unknown-unknown target..."
    rustup target add wasm32-unknown-unknown
fi

# Build all contracts
echo -e "${BLUE}Building all contracts...${NC}"
cargo build --release --target wasm32-unknown-unknown

# Check if build was successful
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Contracts built successfully!${NC}"
    echo ""
    echo "Built contracts:"
    echo "  - escrow.wasm"
    echo "  - reputation.wasm"
    echo ""
    echo "Location: target/wasm32-unknown-unknown/release/"
    echo ""
    
    # Show file sizes
    echo "File sizes:"
    ls -lh target/wasm32-unknown-unknown/release/*.wasm | awk '{print "  - " $9 ": " $5}'
else
    echo ""
    echo "❌ Build failed!"
    exit 1
fi
