# Authentication & Authorization Documentation

## Overview

The Stellarts backend implements a comprehensive role-based access control (RBAC) system using JWT tokens. This document outlines the authentication flow, role permissions, and protected endpoints.

## User Roles

The system supports three distinct user roles:

- **client**: End users who book services from artisans
- **artisan**: Service providers who offer their skills and manage bookings
- **admin**: System administrators with full access to manage users and system operations

## Authentication Flow

### 1. Registration
- **Endpoint**: `POST /api/v1/auth/register`
- **Access**: Public
- **Description**: Users can register with a specific role (client, artisan, or admin)
- **Role Assignment**: Role is set during registration and cannot be changed without admin privileges

### 2. Login
- **Endpoint**: `POST /api/v1/auth/login`
- **Access**: Public
- **Description**: Returns JWT access and refresh tokens upon successful authentication

### 3. Token Refresh
- **Endpoint**: `POST /api/v1/auth/refresh`
- **Access**: Requires valid refresh token
- **Description**: Generates new access token using refresh token

### 4. Logout
- **Endpoint**: `POST /api/v1/auth/logout`
- **Access**: Requires valid JWT token
- **Description**: Blacklists the current token to prevent further use

## Protected Endpoints by Role

### Public Endpoints (No Authentication Required)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/auth/register` | POST | User registration |
| `/api/v1/auth/login` | POST | User login |
| `/api/v1/auth/refresh` | POST | Token refresh |
| `/api/v1/artisans/` | GET | List all artisans |
| `/api/v1/artisans/{artisan_id}/profile` | GET | Get artisan profile |

### Client-Only Endpoints

| Endpoint | Method | Description | Error Response |
|----------|--------|-------------|----------------|
| `/api/v1/bookings/create` | POST | Create new booking | 403 if not client |

### Artisan-Only Endpoints

| Endpoint | Method | Description | Error Response |
|----------|--------|-------------|----------------|
| `/api/v1/artisans/update-profile` | PUT | Update artisan profile | 403 if not artisan |
| `/api/v1/artisans/portfolio/add` | POST | Add portfolio item | 403 if not artisan |
| `/api/v1/artisans/my-portfolio` | GET | Get own portfolio | 403 if not artisan |
| `/api/v1/artisans/my-bookings` | GET | Get assigned bookings | 403 if not artisan |
| `/api/v1/artisans/availability` | PUT | Update availability | 403 if not artisan |

### Admin-Only Endpoints

| Endpoint | Method | Description | Error Response |
|----------|--------|-------------|----------------|
| `/api/v1/admin/users` | GET | List all users | 403 if not admin |
| `/api/v1/admin/users/{user_id}/role` | PUT | Update user role | 403 if not admin |
| `/api/v1/admin/users/{user_id}/status` | PUT | Activate/deactivate user | 403 if not admin |
| `/api/v1/admin/users/{user_id}` | DELETE | Delete user account | 403 if not admin |
| `/api/v1/admin/stats` | GET | Get system statistics | 403 if not admin |
| `/api/v1/users/` | GET | List all users | 403 if not admin |
| `/api/v1/artisans/{artisan_id}` | DELETE | Delete artisan | 403 if not admin |
| `/api/v1/bookings/all` | GET | Get all bookings | 403 if not admin |

### Multi-Role Endpoints

| Endpoint | Method | Allowed Roles | Description |
|----------|--------|---------------|-------------|
| `/api/v1/users/me` | GET | client, artisan, admin | Get own profile |
| `/api/v1/users/{user_id}` | GET | admin OR self | Get user by ID |
| `/api/v1/bookings/my-bookings` | GET | client, artisan | Get own bookings |
| `/api/v1/bookings/{booking_id}/status` | PUT | client, artisan, admin | Update booking status* |

*Note: Booking status updates have additional business logic:
- **Clients**: Can only cancel their own bookings
- **Artisans**: Can update status of bookings assigned to them
- **Admins**: Can update any booking status

## Error Responses

### 401 Unauthorized
Returned when:
- No token provided
- Invalid token format
- Expired token
- Blacklisted/revoked token
- User account is inactive

```json
{
  "detail": "Could not validate credentials",
  "status_code": 401
}
```

### 403 Forbidden
Returned when:
- Valid token but insufficient role permissions
- Attempting to access resources belonging to other users (when not admin)

```json
{
  "detail": "Access denied. Required roles: admin. Your role: client",
  "status_code": 403
}
```

## Security Features

### Token Management
- **JWT Tokens**: Stateless authentication using JSON Web Tokens
- **Token Blacklisting**: Logout functionality blacklists tokens in Redis
- **Refresh Tokens**: Separate refresh tokens for secure token renewal
- **Token Expiration**: Access tokens expire in 30 minutes, refresh tokens in 3 days

### Role Validation
- **Centralized Auth Module**: All role checking logic in `app.core.auth`
- **Dependency Injection**: FastAPI dependencies for clean role enforcement
- **Flexible Permissions**: Support for single-role and multi-role endpoints

### Password Security
- **Argon2 Hashing**: Industry-standard password hashing
- **Password Strength**: Enforced complexity requirements
- **No Plain Text**: Passwords never stored in plain text

## Implementation Details

### Authentication Dependencies

```python
# Basic authentication
from app.core.auth import get_current_active_user

# Role-specific dependencies
from app.core.auth import require_client, require_artisan, require_admin

# Multi-role dependencies
from app.core.auth import require_client_or_artisan, require_artisan_or_admin
```

### Custom Error Classes

```python
# 401 Unauthorized
class AuthenticationError(HTTPException)

# 403 Forbidden
class AuthorizationError(HTTPException)
```

### Usage Examples

```python
# Client-only endpoint
@router.post("/bookings/create")
def create_booking(current_user: User = Depends(require_client)):
    # Only clients can access this endpoint
    pass

# Admin or self access
@router.get("/users/{user_id}")
def get_user(user_id: int, current_user: User = Depends(get_current_active_user)):
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    # Logic here
```

## Testing Role-Based Access

### Test Scenarios

1. **Valid Role Access**: User with correct role can access endpoint
2. **Invalid Role Access**: User with wrong role receives 403 error
3. **No Authentication**: Unauthenticated requests receive 401 error
4. **Expired Token**: Expired tokens receive 401 error
5. **Blacklisted Token**: Logged out tokens receive 401 error
6. **Inactive User**: Inactive user accounts receive 401 error

### Test Data Setup

```python
# Create test users for each role
client_user = {"email": "client@test.com", "role": "client"}
artisan_user = {"email": "artisan@test.com", "role": "artisan"}
admin_user = {"email": "admin@test.com", "role": "admin"}
```

## Migration Notes

When upgrading existing systems:

1. **Database Migration**: Ensure all existing users have a valid role assigned
2. **Default Role**: Consider setting a default role for existing users
3. **Admin Creation**: Ensure at least one admin user exists before deployment
4. **Token Invalidation**: Consider invalidating all existing tokens to force re-authentication

## Security Best Practices

1. **Principle of Least Privilege**: Users only get minimum required permissions
2. **Regular Token Rotation**: Encourage users to log out/in periodically
3. **Monitor Failed Attempts**: Log and monitor authentication failures
4. **Secure Token Storage**: Client applications should store tokens securely
5. **HTTPS Only**: Always use HTTPS in production for token transmission