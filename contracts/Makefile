.PHONY: build test clean deploy install help

# Default target
.DEFAULT_GOAL := help

# Contract names
CONTRACTS = escrow reputation dispute_resolution

help: ## Show this help message
	@echo "StellArts Smart Contracts - Make Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install required tools and dependencies
	@echo "Installing Rust toolchain..."
	@rustup target add wasm32-unknown-unknown
	@echo "Installing Stellar CLI..."
	@cargo install --locked stellar-cli --features opt
	@echo "✅ Installation complete!"

build: ## Build all contracts
	@echo "🔨 Building all contracts..."
	@cargo build --release --target wasm32-unknown-unknown
	@echo "✅ Build complete!"
	@echo ""
	@echo "Contracts built:"
	@ls -lh target/wasm32-unknown-unknown/release/*.wasm | awk '{print "  - " $$9 ": " $$5}'

build-escrow: ## Build escrow contract only
	@echo "🔨 Building escrow contract..."
	@cd escrow && cargo build --release --target wasm32-unknown-unknown
	@echo "✅ Escrow contract built!"

build-reputation: ## Build reputation contract only
	@echo "🔨 Building reputation contract..."
	@cd reputation && cargo build --release --target wasm32-unknown-unknown
	@echo "✅ Reputation contract built!"

build-dispute-resolution: ## Build dispute resolution contract only
	@echo "🔨 Building dispute resolution contract..."
	@cd dispute_resolution && cargo build --release --target wasm32-unknown-unknown
	@echo "✅ Dispute resolution contract built!"

test: ## Run all tests
	@echo "🧪 Running tests..."
	@cargo test
	@echo "✅ All tests passed!"

test-escrow: ## Run escrow contract tests
	@echo "🧪 Testing escrow contract..."
	@cd escrow && cargo test

test-reputation: ## Run reputation contract tests
	@echo "🧪 Testing reputation contract..."
	@cd reputation && cargo test

test-dispute-resolution: ## Run dispute resolution contract tests
	@echo "🧪 Testing dispute resolution contract..."
	@cd dispute_resolution && cargo test

test-coverage: ## Run tests with coverage
	@echo "🧪 Running tests with coverage..."
	@cargo tarpaulin --out Html --output-dir ./coverage
	@echo "✅ Coverage report: ./coverage/index.html"

clean: ## Clean build artifacts
	@echo "🧹 Cleaning build artifacts..."
	@cargo clean
	@echo "✅ Clean complete!"

fmt: ## Format code
	@echo "📝 Formatting code..."
	@cargo fmt --all
	@echo "✅ Format complete!"

lint: ## Run clippy linter
	@echo "🔍 Running clippy..."
	@cargo clippy --all-targets --all-features -- -D warnings
	@echo "✅ Lint complete!"

check: ## Check code without building
	@echo "🔍 Checking code..."
	@cargo check --target wasm32-unknown-unknown
	@echo "✅ Check complete!"

optimize: build ## Optimize wasm files
	@echo "⚡ Optimizing contracts..."
	@stellar contract optimize --wasm target/wasm32-unknown-unknown/release/escrow.wasm
	@stellar contract optimize --wasm target/wasm32-unknown-unknown/release/reputation.wasm
	@stellar contract optimize --wasm target/wasm32-unknown-unknown/release/dispute_resolution.wasm
	@echo "✅ Optimization complete!"

deploy-testnet: build ## Deploy contracts to testnet
	@echo "🚀 Deploying to testnet..."
	@bash deploy.sh testnet

deploy-mainnet: build ## Deploy contracts to mainnet
	@echo "🚀 Deploying to mainnet..."
	@bash deploy.sh mainnet

watch: ## Watch for changes and rebuild
	@echo "👀 Watching for changes..."
	@cargo watch -x 'build --release --target wasm32-unknown-unknown'

doc: ## Generate documentation
	@echo "📚 Generating documentation..."
	@cargo doc --no-deps --open
	@echo "✅ Documentation generated!"

all: clean build test ## Clean, build, and test
	@echo "✅ All tasks complete!"
