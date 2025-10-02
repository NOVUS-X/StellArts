# Manual Testing Guide for Role-Based Permissions

This guide provides step-by-step instructions for manually testing the role-based permission system using curl commands or the interactive API documentation.

## Prerequisites

1. Make sure the application is running:
   ```bash
   docker-compose up -d
   ```

2. Verify the API is accessible:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

## Step 1: Create Test Users

### Create a Client User
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

### Create an Artisan User
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

### Create an Admin User
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@test.com",
    "password": "TestPass123!",
    "role": "admin",
    "full_name": "Test Admin"
  }'
```

## Step 2: Login and Get Tokens

### Login as Client
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@test.com",
    "password": "TestPass123!"
  }'
```
**Save the `access_token` as CLIENT_TOKEN**

### Login as Artisan
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "artisan@test.com",
    "password": "TestPass123!"
  }'
```
**Save the `access_token` as ARTISAN_TOKEN**

### Login as Admin
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@test.com",
    "password": "TestPass123!"
  }'
```
**Save the `access_token` as ADMIN_TOKEN**

## Step 3: Test Role-Based Access

### Test 1: Public Endpoints (No Authentication Required)

**Health Check:**
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```
**Expected: 200 OK**

**Get All Artisans:**
```bash
curl -X GET "http://localhost:8000/api/v1/artisans/"
```
**Expected: 200 OK**

### Test 2: Authentication Required (Should Fail Without Token)

**Get Current User (No Token):**
```bash
curl -X GET "http://localhost:8000/api/v1/users/me"
```
**Expected: 401 Unauthorized**

### Test 3: Client-Only Access

**Get Own Profile (Should Work):**
```bash
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer CLIENT_TOKEN"
```
**Expected: 200 OK**

**Try to Access Admin Panel (Should Fail):**
```bash
curl -X GET "http://localhost:8000/api/v1/admin/users" \
  -H "Authorization: Bearer CLIENT_TOKEN"
```
**Expected: 403 Forbidden**

**Try to Update Artisan Profile (Should Fail):**
```bash
curl -X PUT "http://localhost:8000/api/v1/artisans/update-profile" \
  -H "Authorization: Bearer CLIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bio": "Test bio"}'
```
**Expected: 403 Forbidden**

### Test 4: Artisan-Only Access

**Get Own Profile (Should Work):**
```bash
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer ARTISAN_TOKEN"
```
**Expected: 200 OK**

**Update Own Profile (Should Work):**
```bash
curl -X PUT "http://localhost:8000/api/v1/artisans/update-profile" \
  -H "Authorization: Bearer ARTISAN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bio": "Updated artisan bio",
    "specialties": ["painting", "sculpture"]
  }'
```
**Expected: 200 OK**

**Try to Access Admin Panel (Should Fail):**
```bash
curl -X GET "http://localhost:8000/api/v1/admin/users" \
  -H "Authorization: Bearer ARTISAN_TOKEN"
```
**Expected: 403 Forbidden**

### Test 5: Admin-Only Access

**Get Own Profile (Should Work):**
```bash
curl -X GET "http://localhost:8000/api/v1/users/me" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```
**Expected: 200 OK**

**Access Admin Panel (Should Work):**
```bash
curl -X GET "http://localhost:8000/api/v1/admin/users" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```
**Expected: 200 OK**

**List All Users (Should Work):**
```bash
curl -X GET "http://localhost:8000/api/v1/users/" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```
**Expected: 200 OK**

**Get System Stats (Should Work):**
```bash
curl -X GET "http://localhost:8000/api/v1/admin/stats" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```
**Expected: 200 OK**

### Test 6: Cross-Role Restrictions

**Client Trying Artisan Endpoint:**
```bash
curl -X GET "http://localhost:8000/api/v1/artisans/my-bookings" \
  -H "Authorization: Bearer CLIENT_TOKEN"
```
**Expected: 403 Forbidden**

**Artisan Trying Admin Endpoint:**
```bash
curl -X GET "http://localhost:8000/api/v1/admin/stats" \
  -H "Authorization: Bearer ARTISAN_TOKEN"
```
**Expected: 403 Forbidden**

## Using Interactive API Documentation

Alternatively, you can test using the interactive documentation:

1. **Open your browser and go to:** http://localhost:8000/docs

2. **Click the "Authorize" button** (lock icon in the top right)

3. **Enter your token** in the format: `Bearer YOUR_TOKEN_HERE`

4. **Test different endpoints** by expanding them and clicking "Try it out"

5. **Switch between different user tokens** to test role-based access

## Expected Results Summary

| Endpoint | Client | Artisan | Admin | Public |
|----------|--------|---------|-------|--------|
| `/health` | ✅ | ✅ | ✅ | ✅ |
| `/users/me` | ✅ | ✅ | ✅ | ❌ |
| `/users/` | ❌ | ❌ | ✅ | ❌ |
| `/artisans/` | ✅ | ✅ | ✅ | ✅ |
| `/artisans/update-profile` | ❌ | ✅ | ✅ | ❌ |
| `/artisans/my-bookings` | ❌ | ✅ | ✅ | ❌ |
| `/bookings/my-bookings` | ✅ | ✅ | ✅ | ❌ |
| `/admin/users` | ❌ | ❌ | ✅ | ❌ |
| `/admin/stats` | ❌ | ❌ | ✅ | ❌ |

**Legend:**
- ✅ = Should return 200 OK
- ❌ = Should return 403 Forbidden (or 401 if no token)

## Troubleshooting

### Common Issues:

1. **401 Unauthorized**: Token is missing, expired, or invalid
2. **403 Forbidden**: User doesn't have permission for this endpoint
3. **422 Validation Error**: Request data format is incorrect
4. **500 Internal Server Error**: Check server logs

### Check Server Logs:
```bash
docker-compose logs api
```

### Restart Services:
```bash
docker-compose restart
```