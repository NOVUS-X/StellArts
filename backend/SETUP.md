# Stellarts Backend Setup Guide

## Overview

This guide will help you set up and run the Stellarts backend application with role-based authentication and authorization.

## Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose (recommended)
- PostgreSQL (if running without Docker)
- Redis (if running without Docker)

## Quick Start with Docker (Recommended)

### 1. Clone and Navigate to Project
```bash
cd StellArts
```

### 2. Environment Setup
Copy the example environment file and configure it:
```bash
copy .env.example .env
```

Edit the `.env` file with your configuration:
```env
# Database
DATABASE_URL=postgresql://stellarts:stellarts_dev@localhost:5432/stellarts

# Security (IMPORTANT: Change in production!)
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=3

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_V1_STR=/api/v1
PROJECT_NAME=Stellarts
DEBUG=True

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]
```

### 3. Start Services with Docker
```bash
docker-compose up -d
```

This will start:
- PostgreSQL database on port 5432
- Redis on port 6379
- FastAPI application on port 8000

### 4. Run Database Migrations
```bash
# If running with Docker
docker-compose exec api alembic upgrade head

# Or if running locally
alembic upgrade head
```

### 5. Access the Application
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

## Manual Setup (Without Docker)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Database Setup
Install and start PostgreSQL, then create the database:
```sql
CREATE DATABASE stellarts;
CREATE USER stellarts WITH PASSWORD 'stellarts_dev';
GRANT ALL PRIVILEGES ON DATABASE stellarts TO stellarts;
```

### 3. Redis Setup
Install and start Redis server:
```bash
# Windows (with Redis for Windows)
redis-server

# Linux/Mac
sudo systemctl start redis
```

### 4. Environment Configuration
Create `.env` file with local database URLs:
```env
DATABASE_URL=postgresql://stellarts:stellarts_dev@localhost:5432/stellarts
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-super-secret-key-here
```

### 5. Run Database Migrations
```bash
alembic upgrade head
```

### 6. Start the Application
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing the Role-Based Authentication

### 1. Create Test Users

First, register users with different roles:

**Create a Client:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@test.com",
    "password": "TestPass123!",
    "role": "client",
    "full_name": "Test Client"
  }'
```

**Create an Artisan:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "artisan@test.com",
    "password": "TestPass123!",
    "role": "artisan",
    "full_name": "Test Artisan"
  }'
```

**Create an Admin (trusted environment only):**
```bash
python scripts/create_admin.py --email admin@test.com --password "TestPass123!"
```

Public registration only allows `"client"` and `"artisan"` roles.

### 2. Login and Get Tokens

Login as each user to get JWT tokens:

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@test.com",
    "password": "TestPass123!"
  }'
```

Save the `access_token` from the response for testing.

### 3. Test Role-Based Endpoints

**Test Client-Only Endpoint:**
```bash
# This should work with client token
curl -X POST "http://localhost:8000/api/v1/bookings/create" \
  -H "Authorization: Bearer YOUR_CLIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service": "painting", "date": "2024-01-15"}'

# This should fail (403) with artisan token
curl -X POST "http://localhost:8000/api/v1/bookings/create" \
  -H "Authorization: Bearer YOUR_ARTISAN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service": "painting", "date": "2024-01-15"}'
```

**Test Artisan-Only Endpoint:**
```bash
# This should work with artisan token
curl -X PUT "http://localhost:8000/api/v1/artisans/update-profile" \
  -H "Authorization: Bearer YOUR_ARTISAN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bio": "Updated bio", "specialties": ["painting"]}'

# This should fail (403) with client token
curl -X PUT "http://localhost:8000/api/v1/artisans/update-profile" \
  -H "Authorization: Bearer YOUR_CLIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bio": "Updated bio", "specialties": ["painting"]}'
```

**Test Admin-Only Endpoint:**
```bash
# This should work with admin token
curl -X GET "http://localhost:8000/api/v1/admin/users" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# This should fail (403) with client or artisan token
curl -X GET "http://localhost:8000/api/v1/admin/users" \
  -H "Authorization: Bearer YOUR_CLIENT_TOKEN"
```

## API Documentation

Once the application is running, you can explore all endpoints and test the authentication system using the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Using the Interactive Docs

1. Go to http://localhost:8000/docs
2. Click on "Authorize" button (lock icon)
3. Enter your JWT token in the format: `Bearer YOUR_TOKEN_HERE`
4. Now you can test protected endpoints directly from the documentation

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Authentication Tests Only
```bash
pytest app/tests/test_auth_roles.py -v
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=html
```

## Development Commands

### Database Operations
```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Code Quality
```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking (if using mypy)
mypy app/
```

## Production Deployment

### Environment Variables for Production

```env
# Security - CRITICAL: Use strong, unique values
SECRET_KEY=your-super-strong-secret-key-minimum-32-characters
DEBUG=False

# Database - Use production database
DATABASE_URL=postgresql://user:password@prod-db-host:5432/stellarts

# Redis - Use production Redis
REDIS_URL=redis://prod-redis-host:6379/0

# CORS - Restrict to your frontend domains
BACKEND_CORS_ORIGINS=["https://yourdomain.com"]

# Token expiration - Consider shorter times for production
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Security Checklist

- [ ] Change default SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Use HTTPS in production
- [ ] Restrict CORS origins
- [ ] Use strong database passwords
- [ ] Enable database SSL
- [ ] Set up proper logging
- [ ] Configure rate limiting
- [ ] Set up monitoring

## Troubleshooting

### Common Issues

**1. Database Connection Error**
```
sqlalchemy.exc.OperationalError: could not connect to server
```
- Ensure PostgreSQL is running
- Check DATABASE_URL in .env file
- Verify database credentials

**2. Redis Connection Error**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```
- Ensure Redis is running
- Check REDIS_URL in .env file
- Verify Redis is accessible

**3. JWT Token Errors**
```
401 Unauthorized: Could not validate credentials
```
- Check if token is expired
- Verify SECRET_KEY matches between token creation and validation
- Ensure token format is correct (Bearer TOKEN)

**4. Permission Denied (403)**
```
403 Forbidden: Insufficient permissions
```
- Verify user has correct role for the endpoint
- Check if user account is active
- Ensure token belongs to the correct user

### Logs and Debugging

**View Docker Logs:**
```bash
docker-compose logs api
docker-compose logs db
docker-compose logs redis
```

**Enable Debug Mode:**
Set `DEBUG=True` in .env file for detailed error messages.

## Support

For issues and questions:
1. Check the logs for error details
2. Verify your environment configuration
3. Test with the interactive API documentation
4. Review the authentication documentation in `/docs/auth.md`

## Next Steps

After setting up the basic authentication system, consider:

1. **Email Verification**: Implement email verification for new users
2. **Password Reset**: Add password reset functionality
3. **Rate Limiting**: Implement API rate limiting
4. **Audit Logging**: Add audit trails for admin actions
5. **Two-Factor Authentication**: Add 2FA for enhanced security
6. **API Versioning**: Plan for future API versions
7. **Monitoring**: Set up application monitoring and alerting
