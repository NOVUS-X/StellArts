#!/bin/bash

# Test script for StellArts smart contracts

set -e

echo "🧪 Testing StellArts Smart Contracts..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Run all tests
echo -e "${BLUE}Running all tests...${NC}"
cargo test

# Check if tests passed
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo ""
    echo "❌ Tests failed!"
    exit 1
fi

# Run tests with coverage (if tarpaulin is installed)
if command -v cargo-tarpaulin &> /dev/null; then
    echo ""
    echo -e "${BLUE}Running tests with coverage...${NC}"
    cargo tarpaulin --out Html --output-dir ./coverage
    echo ""
    echo -e "${GREEN}Coverage report generated: ./coverage/index.html${NC}"
fi
