#!/bin/bash

# Post-create script for StellArts DevContainer

set -e

echo "Setting up StellArts development environment..."

# Install Python dependencies
echo "Installing Python dependencies..."
cd /workspaces/StellArts/backend
pip install -r requirements.txt

# Install Node dependencies
echo "Installing Node dependencies..."
cd /workspaces/StellArts/frontend
npm install

# Install Rust toolchain for Soroban contracts
echo "Setting up Rust toolchain..."
cd /workspaces/StellArts/contracts
rustup component add rustfmt clippy
cargo install --locked soroban-cli@21.0.0

# Install stellar CLI
echo "Installing Stellar CLI..."
cargo install --locked stellar-cli@21.0.0

# Create .env files from examples if they don't exist
cd /workspaces/StellArts/backend
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

cd /workspaces/StellArts/frontend
if [ ! -f .env.local ]; then
    cp .env.example .env.local
    echo "Created .env.local from .env.example"
fi

echo "DevContainer setup complete!"
echo "You can now:"
echo "  - Run backend: cd /workspaces/StellArts/backend && make up"
echo "  - Run frontend: cd /workspaces/StellArts/frontend && npm run dev"
echo "  - Build contracts: cd /workspaces/StellArts/contracts && make build"
