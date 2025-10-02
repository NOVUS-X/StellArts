# Stellarts Backend

A scalable, production-ready FastAPI backend for the Stellarts platform - connecting artisans with clients through a robust API layer.

## Features

- **FastAPI Framework**: Modern, fast web framework for building APIs
- **Modular Architecture**: Clean separation of concerns with organized directory structure
- **Database Integration**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT-based authentication system
- **API Versioning**: Versioned API endpoints for smooth upgrades
- **Containerized**: Docker and docker-compose for easy deployment
- **CI/CD Pipeline**: GitHub Actions for automated testing and deployment
- **Comprehensive Testing**: Pytest with coverage reporting
- **Code Quality**: Linting and formatting with flake8, ruff, and black

## 📁 Project Structure

```
app/
├── api/
│   └── v1/
│       ├── endpoints/          # API route handlers
│       │   └── health.py      # Health check endpoint
│       └── api.py             # API router configuration
├── core/
│   ├── config.py              # Application configuration
│   └── security.py            # Security utilities
├── db/
│   ├── base.py                # Database base configuration
│   └── session.py             # Database session management
├── models/                    # SQLAlchemy models
├── schemas/                   # Pydantic schemas
├── services/                  # Business logic
├── tests/                     # Test files
└── main.py                    # FastAPI application entry point
```

## 🛠️ Quick Start

### Prerequisites

- Docker and Docker Compose
- Make (optional, for convenience commands)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd StellArts
```

### 2. Environment Configuration

```bash
# Copy environment template
make dev-setup
# OR manually:
cp env.example .env
```

Edit `.env` file with your configuration:

```env
DATABASE_URL=postgresql://stellarts:stellarts_dev@db:5432/stellarts_db
SECRET_KEY=your-secret-key-here
DEBUG=True
```

### 3. Start the Application

```bash
# Start all services
make up

# OR using docker-compose directly:
docker-compose up -d
```

### 4. Verify Installation

- API Health Check: http://localhost:8000/api/v1/health
- API Documentation: http://localhost:8000/docs
- API Root: http://localhost:8000/

## 🔧 Development

### Available Commands

```bash
# Development
make up              # Start all services
make down            # Stop all services
make logs            # View logs
make shell           # Open shell in API container

# Testing
make test            # Run tests
make test-cov        # Run tests with coverage

# Code Quality
make lint            # Run linting
make format          # Format code

# Database
make db-shell        # Open PostgreSQL shell
make migrate         # Run database migrations
make migration m="description"  # Create new migration

# Cleanup
make clean           # Clean containers and volumes
```

### Development Workflow

1. **Make Changes**: Edit code in your favorite editor
2. **Test**: Run `make test` to ensure tests pass
3. **Lint**: Run `make lint` to check code quality
4. **Format**: Run `make format` to format code
5. **Commit**: Commit your changes

### Database Migrations

```bash
# Create a new migration
make migration m="add user table"

# Apply migrations
make migrate
```

## Testing

The project uses pytest for testing with comprehensive coverage:

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run specific test file
docker-compose exec api pytest app/tests/test_main.py -v

# Run tests with specific marker
docker-compose exec api pytest -m "not slow" -v
```

## 🏗️ CI/CD Pipeline

The project uses GitHub Actions for continuous integration:

- **Linting**: Automated code quality checks with flake8 and ruff
- **Testing**: Automated test execution with pytest
- **Docker**: Automated Docker image building and testing
- **Coverage**: Code coverage reporting with codecov

### Branch Protection

- All code must pass CI checks before merging
- Pull requests require review
- Main branch is protected

## 🐳 Docker

### Development Environment

```bash
# Start development services
docker-compose up -d

# View logs
docker-compose logs -f api

# Rebuild after dependency changes
docker-compose build --no-cache
```

### Production Environment

```bash
# Start production services
make prod
# OR
docker-compose up -d api-prod db
```

## 📊 API Documentation

- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/api/v1/openapi.json

### Key Endpoints

- `GET /` - Root endpoint with API information
- `GET /api/v1/health` - Health check with database status
- `GET /docs` - Interactive API documentation

## Security

- JWT-based authentication
- Password hashing with bcrypt
- CORS configuration
- Environment-based configuration
- Secure defaults in production

## Deployment

### Environment Variables

Required environment variables for production:

```env
DATABASE_URL=postgresql://user:pass@host:port/db
SECRET_KEY=secure-random-key
DEBUG=False
BACKEND_CORS_ORIGINS=["https://yourdomain.com"]
```

### Production Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Configure production database
- [ ] Set `DEBUG=False`
- [ ] Configure CORS origins
- [ ] Set up SSL/TLS
- [ ] Configure logging
- [ ] Set up monitoring

##  Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Write tests for new features
- Update documentation as needed
- Ensure all CI checks pass

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## Troubleshooting

### Common Issues

**Database Connection Issues**
```bash
# Check if database is running
docker-compose ps

# Check database logs
docker-compose logs db

# Reset database
make clean && make up
```

**Port Already in Use**
```bash
# Stop conflicting services
sudo lsof -i :8000
sudo kill -9 <PID>

# Or change port in docker-compose.yml
```

**Permission Issues**
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
```