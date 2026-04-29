# Script to deploy Soroban contracts to local standalone network (Windows PowerShell)
# Usage: .\scripts\deploy_local.ps1

$ErrorActionPreference = "Stop"

Write-Host "🚀 Deploying contracts to local Soroban network..." -ForegroundColor Cyan

# Configuration
$RpcUrl = if ($env:STELLAR_RPC_URL) { $env:STELLAR_RPC_URL } else { "http://localhost:8002/soroban/rpc" }
$NetworkPassphrase = if ($env:STELLAR_NETWORK_PASSPHRASE) { $env:STELLAR_NETWORK_PASSPHRASE } else { "Standalone Network ; September 2022" }
$Network = "standalone"

# Check if stellar CLI is installed
try {
    $null = Get-Command stellar -ErrorAction Stop
} catch {
    Write-Host "❌ stellar CLI not found. Please install it first:" -ForegroundColor Red
    Write-Host "   cargo install --locked stellar-cli" -ForegroundColor Yellow
    exit 1
}

# Check if the network is running
Write-Host "📡 Checking if local network is available..." -ForegroundColor Cyan
try {
    $healthCheck = Invoke-RestMethod -Uri $RpcUrl -Method Post -ContentType "application/json" -Body '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' -ErrorAction Stop
    if ($healthCheck.result.status -eq "healthy") {
        Write-Host "✅ Local network is healthy" -ForegroundColor Green
    } else {
        throw "Network not healthy"
    }
} catch {
    Write-Host "❌ Local Soroban network is not running or not accessible at $RpcUrl" -ForegroundColor Red
    Write-Host "   Make sure to run: docker-compose up -d soroban-rpc" -ForegroundColor Yellow
    exit 1
}

# Generate or use existing identity
Write-Host "🔑 Setting up identity..." -ForegroundColor Cyan
$existingKeys = stellar keys ls 2>$null
if ($existingKeys -notcontains "admin") {
    Write-Host "   Creating admin identity..." -ForegroundColor Yellow
    stellar keys generate admin --network $Network --rpc-url $RpcUrl
}

$AdminKey = stellar keys address admin
Write-Host "   Admin key: $AdminKey" -ForegroundColor Green

# Fund the identity from the standalone network's friendbot
Write-Host "💰 Funding admin identity from friendbot..." -ForegroundColor Cyan
$FriendbotUrl = "http://localhost:8003/friendbot?addr=$AdminKey"
try {
    $fundResult = Invoke-RestMethod -Uri $FriendbotUrl -ErrorAction Stop
    Write-Host "✅ Admin identity funded" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Friendbot funding may have failed (this is okay if already funded)" -ForegroundColor Yellow
}

# Deploy Escrow Contract
Write-Host ""
Write-Host "📦 Deploying Escrow contract..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\..\contracts"

$EscrowWasm = "target\wasm32-unknown-unknown\release\escrow.wasm"
if (-not (Test-Path $EscrowWasm)) {
    Write-Host "   Building escrow contract..." -ForegroundColor Yellow
    make build
}

$EscrowHash = stellar contract install `
    --network $Network `
    --rpc-url $RpcUrl `
    --source admin `
    --wasm $EscrowWasm

Write-Host "   Escrow WASM hash: $EscrowHash" -ForegroundColor Green

$EscrowContractId = stellar contract deploy `
    --network $Network `
    --rpc-url $RpcUrl `
    --source admin `
    --wasm-hash $EscrowHash

Write-Host "✅ Escrow contract deployed: $EscrowContractId" -ForegroundColor Green

# Deploy Reputation Contract
Write-Host ""
Write-Host "📦 Deploying Reputation contract..." -ForegroundColor Cyan

$ReputationWasm = "target\wasm32-unknown-unknown\release\reputation.wasm"
if (-not (Test-Path $ReputationWasm)) {
    Write-Host "   Building reputation contract..." -ForegroundColor Yellow
    make build
}

$ReputationHash = stellar contract install `
    --network $Network `
    --rpc-url $RpcUrl `
    --source admin `
    --wasm $ReputationWasm

Write-Host "   Reputation WASM hash: $ReputationHash" -ForegroundColor Green

$ReputationContractId = stellar contract deploy `
    --network $Network `
    --rpc-url $RpcUrl `
    --source admin `
    --wasm-hash $ReputationHash

Write-Host "✅ Reputation contract deployed: $ReputationContractId" -ForegroundColor Green

# Update backend .env file
Write-Host ""
Write-Host "📝 Updating backend configuration..." -ForegroundColor Cyan
$BackendEnv = Join-Path $PSScriptRoot "..\..\backend\.env"

if (Test-Path $BackendEnv) {
    $envContent = Get-Content $BackendEnv -Raw
    
    # Update or add values
    if ($envContent -match "STELLAR_RPC_URL=") {
        $envContent = $envContent -replace "STELLAR_RPC_URL=.*", "STELLAR_RPC_URL=$RpcUrl"
    } else {
        $envContent += "`nSTELLAR_RPC_URL=$RpcUrl"
    }
    
    if ($envContent -match "ESCROW_CONTRACT_ID=") {
        $envContent = $envContent -replace "ESCROW_CONTRACT_ID=.*", "ESCROW_CONTRACT_ID=$EscrowContractId"
    } else {
        $envContent += "`nESCROW_CONTRACT_ID=$EscrowContractId"
    }
    
    if ($envContent -match "REPUTATION_CONTRACT_ID=") {
        $envContent = $envContent -replace "REPUTATION_CONTRACT_ID=.*", "REPUTATION_CONTRACT_ID=$ReputationContractId"
    } else {
        $envContent += "`nREPUTATION_CONTRACT_ID=$ReputationContractId"
    }
    
    $envContent | Set-Content $BackendEnv -NoNewline
    Write-Host "✅ Updated $BackendEnv" -ForegroundColor Green
} else {
    Write-Host "⚠️  Backend .env file not found at $BackendEnv" -ForegroundColor Yellow
    Write-Host "   Please manually set these values:" -ForegroundColor Yellow
    Write-Host "   ESCROW_CONTRACT_ID=$EscrowContractId" -ForegroundColor Yellow
    Write-Host "   REPUTATION_CONTRACT_ID=$ReputationContractId" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "🎉 Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Contract IDs:" -ForegroundColor Cyan
Write-Host "  Escrow:     $EscrowContractId" -ForegroundColor White
Write-Host "  Reputation: $ReputationContractId" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Restart your backend to use the new contract IDs" -ForegroundColor White
Write-Host "  2. Update frontend configuration if needed" -ForegroundColor White
Write-Host "  3. Test contract interactions" -ForegroundColor White
