# Contributing to StellArts

Thank you for your interest in contributing to StellArts! This guide will help you set up the full stack development environment locally.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

### Docker & Docker Compose
- **Docker Desktop** (recommended): Download from [docker.com](https://www.docker.com/products/docker-desktop/)
- **Docker Compose**: Usually included with Docker Desktop

### Node.js
- **Node.js 18+**: Download from [nodejs.org](https://nodejs.org/) or use a version manager like nvm
- Verify installation: `node --version` and `npm --version`

### Rust & Soroban CLI
- **Rust 1.75.0+**: Install via [rustup.rs](https://rustup.rs/)
- **Stellar CLI**: Install with `cargo install --locked stellar-cli --features opt`
- **Windows users**: Follow the [Windows setup guide](./contracts/WINDOWS_SETUP.md) for additional requirements

Verify installations:
```bash
rustc --version
cargo --version
stellar --version
```

## Development Environment Setup

### Backend Setup (FastAPI)

The backend uses FastAPI with PostgreSQL and Redis.

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Set up environment variables:
   ```bash
   copy .env.example .env
   # On Unix/Mac: cp .env.example .env
   ```
   Edit the `.env` file with your configuration. The defaults should work for local development.

3. Start the services with Docker:
   ```bash
   docker-compose up -d
   ```
   This will start:
   - PostgreSQL database on port 5432
   - Redis on port 6379
   - FastAPI application on port 8000

4. Run database migrations:
   ```bash
   docker-compose exec api alembic upgrade head
   ```

5. Access the application:
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/api/v1/health

### Frontend Setup (Next.js)

The frontend is built with Next.js 15, TypeScript, and Tailwind CSS.

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Set up environment variables:
   ```bash
   copy .env.example .env.local
   # On Unix/Mac: cp .env.example .env.local
   ```
   The defaults should work for local development.

4. Start the development server:
   ```bash
   npm run dev
   ```

5. Open your browser to http://localhost:3000

### Smart Contracts Setup (Soroban)

The smart contracts are written in Rust and deployed to Stellar.

1. Navigate to the contracts directory:
   ```bash
   cd contracts
   ```

2. Add the WebAssembly target:
   ```bash
   rustup target add wasm32-unknown-unknown
   ```

3. Build the contracts:
   ```bash
   cargo build --release --target wasm32-unknown-unknown
   ```

4. Run tests:
   ```bash
   cargo test
   ```

5. (Optional) Optimize for deployment:
   ```bash
   stellar contract optimize --wasm target/wasm32-unknown-unknown/release/escrow.wasm
   stellar contract optimize --wasm target/wasm32-unknown-unknown/release/reputation.wasm
   ```

## Testing Your Setup

### Backend Tests
```bash
cd backend
make test
# Or: pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Contract Tests
```bash
cd contracts
cargo test
```

## Common Issues

### Docker Issues

**Port conflicts**: If ports 5432, 6379, or 8000 are already in use, stop conflicting services or modify docker-compose.yml.

**Permission denied on Windows**: Ensure Docker Desktop is running with administrator privileges.

**Docker Compose not found**: Install Docker Desktop which includes Compose, or install Compose separately.

### Node.js Issues

**npm install fails**: Clear npm cache with `npm cache clean --force` and try again. Ensure Node.js version is 18+.

**Port 3000 in use**: Change the port with `npm run dev -- -p 3001` or stop the conflicting service.

### Rust/Soroban Issues

**Linker errors on Windows**: Install Visual Studio Build Tools as described in [contracts/WINDOWS_SETUP.md](./contracts/WINDOWS_SETUP.md).

**wasm32 target missing**: Run `rustup target add wasm32-unknown-unknown`.

**Stellar CLI not found**: Ensure `~/.cargo/bin` is in your PATH, or use the full path to the stellar executable.

**Slow compilation**: Add exclusions in Windows Defender for your Rust and project directories.

### Database Issues

**Migration failures**: Ensure PostgreSQL is running and accessible. Check DATABASE_URL in .env.

**Connection refused**: Verify Docker containers are running with `docker-compose ps`.

### General Issues

**Environment variables not loading**: Restart your terminal/command prompt after setting environment variables.

**File permission issues**: On Windows, try running commands as Administrator. On Unix/Mac, check file permissions.

**Antivirus interference**: Some antivirus software may interfere with builds. Add exclusions for project directories.

## Development Workflow

1. **Fork and Clone**: Fork the repository and clone your fork
2. **Create Feature Branch**: `git checkout -b feature/your-feature-name`
3. **Make Changes**: Follow the existing code style and conventions
4. **Test Thoroughly**: Run tests for all components you modified
5. **Commit Changes**: Use clear, descriptive commit messages
6. **Push and Create PR**: Push to your fork and create a pull request

## Getting Help

- **Issues**: Check existing GitHub issues for similar problems
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Refer to README files in each component directory
- **Code of Conduct**: Please read and follow our Code of Conduct