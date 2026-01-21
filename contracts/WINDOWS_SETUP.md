# Windows Setup Guide for StellArts Contracts

This guide helps Windows users set up the development environment for Stellar Soroban smart contracts.

## Prerequisites Installation

### 1. Install Visual Studio Build Tools

The Rust toolchain on Windows requires the MSVC linker. Install one of the following:

**Option A: Visual Studio 2022 Community (Recommended)**
1. Download from: https://visualstudio.microsoft.com/downloads/
2. During installation, select "Desktop development with C++"
3. Ensure "MSVC v143 - VS 2022 C++ x64/x86 build tools" is selected
4. Ensure "Windows 10/11 SDK" is selected

**Option B: Build Tools for Visual Studio**
1. Download from: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
2. Install "Desktop development with C++"
3. Install "Windows 10/11 SDK"

### 2. Install Rust

```powershell
# Download and run rustup-init.exe from https://rustup.rs/
# Or use winget:
winget install Rustlang.Rustup
```

After installation, restart your terminal.

### 3. Add wasm32 Target

```powershell
rustup target add wasm32-unknown-unknown
```

### 4. Install Stellar CLI

```powershell
cargo install --locked stellar-cli --features opt
```

## Verify Installation

```powershell
# Check Rust version
rustc --version

# Check cargo version
cargo --version

# Check wasm32 target
rustup target list | Select-String "wasm32-unknown-unknown"

# Check Stellar CLI
stellar --version
```

## Building Contracts

### Using Cargo

```powershell
# Navigate to contracts directory
cd c:\Users\HP\Desktop\StellArts\contracts

# Build all contracts
cargo build --release --target wasm32-unknown-unknown

# Build specific contract
cd escrow
cargo build --release --target wasm32-unknown-unknown
```

### Using Make (if you have Make installed)

```powershell
# Install Make via Chocolatey
choco install make

# Then use:
make build
make test
```

## Testing Contracts

```powershell
# Run all tests
cargo test

# Run tests for specific contract
cd escrow
cargo test -- --nocapture
```

## Common Issues

### Issue: "linker `link.exe` not found"

**Solution**: Install Visual Studio Build Tools as described above.

### Issue: "error: toolchain 'stable-x86_64-pc-windows-msvc' does not support target 'wasm32-unknown-unknown'"

**Solution**: 
```powershell
rustup target add wasm32-unknown-unknown
```

### Issue: PowerShell execution policy error

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: Cargo build is slow

**Solution**: Add exclusion to Windows Defender for your Rust directories:
1. Open Windows Security
2. Go to Virus & threat protection
3. Add exclusions for:
   - `C:\Users\<YourUsername>\.cargo`
   - `C:\Users\<YourUsername>\Desktop\StellArts\contracts\target`

## Using WSL (Alternative Approach)

If you prefer, you can use Windows Subsystem for Linux:

```powershell
# Install WSL2
wsl --install

# After WSL is installed, open Ubuntu and run:
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustup target add wasm32-unknown-unknown
cargo install --locked stellar-cli --features opt
```

Then navigate to your project:
```bash
cd /mnt/c/Users/HP/Desktop/StellArts/contracts
cargo build --release --target wasm32-unknown-unknown
```

## Development Workflow

1. **Write Code**: Edit `.rs` files in `escrow/src/` or `reputation/src/`
2. **Run Tests**: `cargo test`
3. **Build**: `cargo build --release --target wasm32-unknown-unknown`
4. **Deploy**: Use Stellar CLI to deploy to testnet/mainnet

## Next Steps

- Read the [main README](README.md) for contract documentation
- Explore the [escrow contract](escrow/src/lib.rs)
- Explore the [reputation contract](reputation/src/lib.rs)
- Check out [Soroban documentation](https://soroban.stellar.org/docs)

## Support

If you encounter issues:
1. Check the [Stellar Developer Discord](https://discord.gg/stellardev)
2. Review [Soroban documentation](https://soroban.stellar.org/docs)
3. Open an issue on GitHub
