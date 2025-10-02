#!/usr/bin/env python3
"""
Role-Based Permission Testing Script for Stellarts API

This script tests the role-based access control implementation by:
1. Creating users with different roles (client, artisan, admin)
2. Testing access to various endpoints with different user tokens
3. Verifying that permissions are enforced correctly

Usage: python test_roles.py
"""

import requests
import json
import time
from typing import Dict, Optional

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class RoleTestSuite:
    def __init__(self):
        self.tokens = {}
        self.users = {}
        self.test_results = []
        
    def print_header(self, text: str):
        """Print a formatted header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")
        
    def print_test(self, test_name: str, expected: str, actual: str, passed: bool):
        """Print test result"""
        status = f"{Colors.GREEN}✓ PASS" if passed else f"{Colors.RED}✗ FAIL"
        print(f"{status}{Colors.END} {test_name}")
        print(f"  Expected: {expected}")
        print(f"  Actual: {actual}")
        if not passed:
            print(f"  {Colors.RED}❌ Test failed!{Colors.END}")
        print()
        
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'expected': expected,
            'actual': actual
        })
    
    def check_health(self) -> bool:
        """Check if the API is running"""
        try:
            response = requests.get(f"{API_BASE}/health", timeout=5)
            if response.status_code == 200:
                print(f"{Colors.GREEN}✓ API is running at {BASE_URL}{Colors.END}")
                return True
            else:
                print(f"{Colors.RED}✗ API health check failed: {response.status_code}{Colors.END}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"{Colors.RED}✗ Cannot connect to API: {e}{Colors.END}")
            print(f"{Colors.YELLOW}Make sure the API is running with: docker-compose up -d{Colors.END}")
            return False
    
    def register_user(self, email: str, password: str, role: str, full_name: str) -> bool:
        """Register a new user"""
        data = {
            "email": email,
            "password": password,
            "role": role,
            "full_name": full_name
        }
        
        try:
            response = requests.post(f"{API_BASE}/auth/register", json=data)
            if response.status_code == 201:
                print(f"{Colors.GREEN}✓ Registered {role}: {email}{Colors.END}")
                return True
            elif response.status_code == 400 and "already registered" in response.text:
                print(f"{Colors.YELLOW}⚠ User {email} already exists{Colors.END}")
                return True
            else:
                print(f"{Colors.RED}✗ Failed to register {email}: {response.status_code} - {response.text}{Colors.END}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"{Colors.RED}✗ Registration error for {email}: {e}{Colors.END}")
            return False
    
    def login_user(self, email: str, password: str) -> Optional[str]:
        """Login user and return access token"""
        data = {
            "email": email,
            "password": password
        }
        
        try:
            response = requests.post(f"{API_BASE}/auth/login", json=data)
            if response.status_code == 200:
                token = response.json()["access_token"]
                print(f"{Colors.GREEN}✓ Logged in: {email}{Colors.END}")
                return token
            else:
                print(f"{Colors.RED}✗ Login failed for {email}: {response.status_code} - {response.text}{Colors.END}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"{Colors.RED}✗ Login error for {email}: {e}{Colors.END}")
            return None
    
    def make_request(self, method: str, endpoint: str, token: str = None, data: dict = None) -> requests.Response:
        """Make an authenticated request"""
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        url = f"{API_BASE}{endpoint}"
        
        try:
            if method.upper() == "GET":
                return requests.get(url, headers=headers)
            elif method.upper() == "POST":
                return requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                return requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                return requests.delete(url, headers=headers)
        except requests.exceptions.RequestException as e:
            print(f"{Colors.RED}Request error: {e}{Colors.END}")
            return None
    
    def test_endpoint_access(self, endpoint: str, method: str, role: str, expected_status: int, 
                           test_name: str, data: dict = None):
        """Test access to a specific endpoint with a specific role"""
        token = self.tokens.get(role)
        if not token:
            print(f"{Colors.RED}✗ No token available for role: {role}{Colors.END}")
            return
        
        response = self.make_request(method, endpoint, token, data)
        if response is None:
            self.print_test(test_name, f"Status {expected_status}", "Request failed", False)
            return
        
        actual_status = response.status_code
        passed = actual_status == expected_status
        
        status_text = {
            200: "200 OK (Success)",
            201: "201 Created (Success)",
            401: "401 Unauthorized (No/Invalid token)",
            403: "403 Forbidden (Insufficient permissions)",
            404: "404 Not Found",
            422: "422 Validation Error"
        }.get(actual_status, f"{actual_status} (Unknown)")
        
        expected_text = {
            200: "200 OK (Success)",
            201: "201 Created (Success)",
            401: "401 Unauthorized",
            403: "403 Forbidden",
            404: "404 Not Found",
            422: "422 Validation Error"
        }.get(expected_status, f"{expected_status}")
        
        self.print_test(test_name, expected_text, status_text, passed)
    
    def setup_test_users(self):
        """Create test users with different roles"""
        self.print_header("SETTING UP TEST USERS")
        
        # Test users
        test_users = [
            ("client@test.com", "TestPass123!", "client", "Test Client"),
            ("artisan@test.com", "TestPass123!", "artisan", "Test Artisan"),
            ("admin@test.com", "TestPass123!", "admin", "Test Admin")
        ]
        
        # Register users
        for email, password, role, full_name in test_users:
            self.register_user(email, password, role, full_name)
            time.sleep(0.5)  # Small delay between registrations
        
        print()
        
        # Login users and get tokens
        for email, password, role, full_name in test_users:
            token = self.login_user(email, password)
            if token:
                self.tokens[role] = token
                self.users[role] = {"email": email, "password": password}
            time.sleep(0.5)  # Small delay between logins
    
    def test_public_endpoints(self):
        """Test endpoints that should be accessible to everyone"""
        self.print_header("TESTING PUBLIC ENDPOINTS")
        
        # Health check (no auth required)
        response = requests.get(f"{API_BASE}/health")
        passed = response.status_code == 200
        self.print_test("Health Check", "200 OK", f"{response.status_code} {response.reason}", passed)
        
        # Get all artisans (public)
        response = requests.get(f"{API_BASE}/artisans/")
        passed = response.status_code == 200
        self.print_test("Get All Artisans (Public)", "200 OK", f"{response.status_code} {response.reason}", passed)
    
    def test_authentication_required(self):
        """Test that protected endpoints require authentication"""
        self.print_header("TESTING AUTHENTICATION REQUIREMENTS")
        
        # Test endpoints without token (should get 401)
        endpoints = [
            ("/users/me", "GET"),
            ("/bookings/my-bookings", "GET"),
            ("/artisans/update-profile", "PUT"),
            ("/admin/users", "GET")
        ]
        
        for endpoint, method in endpoints:
            response = self.make_request(method, endpoint)
            if response:
                passed = response.status_code == 401
                self.print_test(f"{method} {endpoint} (No Token)", "401 Unauthorized", 
                              f"{response.status_code} {response.reason}", passed)
    
    def test_client_permissions(self):
        """Test client-specific permissions"""
        self.print_header("TESTING CLIENT PERMISSIONS")
        
        # Client should be able to access these
        self.test_endpoint_access("/users/me", "GET", "client", 200, "Client: Get Own Profile")
        self.test_endpoint_access("/bookings/my-bookings", "GET", "client", 200, "Client: Get Own Bookings")
        
        # Client should NOT be able to access these (403 Forbidden)
        self.test_endpoint_access("/artisans/update-profile", "PUT", "client", 403, 
                                "Client: Update Artisan Profile (Should Fail)", 
                                {"bio": "Test bio"})
        self.test_endpoint_access("/admin/users", "GET", "client", 403, 
                                "Client: Access Admin Panel (Should Fail)")
        self.test_endpoint_access("/users/", "GET", "client", 403, 
                                "Client: List All Users (Should Fail)")
    
    def test_artisan_permissions(self):
        """Test artisan-specific permissions"""
        self.print_header("TESTING ARTISAN PERMISSIONS")
        
        # Artisan should be able to access these
        self.test_endpoint_access("/users/me", "GET", "artisan", 200, "Artisan: Get Own Profile")
        self.test_endpoint_access("/artisans/my-bookings", "GET", "artisan", 200, "Artisan: Get Own Bookings")
        self.test_endpoint_access("/artisans/update-profile", "PUT", "artisan", 200, 
                                "Artisan: Update Own Profile", 
                                {"bio": "Updated artisan bio", "specialties": ["painting"]})
        
        # Artisan should NOT be able to access these (403 Forbidden)
        self.test_endpoint_access("/admin/users", "GET", "artisan", 403, 
                                "Artisan: Access Admin Panel (Should Fail)")
        self.test_endpoint_access("/users/", "GET", "artisan", 403, 
                                "Artisan: List All Users (Should Fail)")
    
    def test_admin_permissions(self):
        """Test admin-specific permissions"""
        self.print_header("TESTING ADMIN PERMISSIONS")
        
        # Admin should be able to access everything
        self.test_endpoint_access("/users/me", "GET", "admin", 200, "Admin: Get Own Profile")
        self.test_endpoint_access("/admin/users", "GET", "admin", 200, "Admin: List All Users")
        self.test_endpoint_access("/users/", "GET", "admin", 200, "Admin: List Users via User Endpoint")
        self.test_endpoint_access("/admin/stats", "GET", "admin", 200, "Admin: Get System Stats")
        
        # Admin should be able to manage users
        # Note: We'll test with a non-existent user ID to avoid affecting real data
        self.test_endpoint_access("/admin/users/999/role", "PUT", "admin", 404, 
                                "Admin: Update User Role (Non-existent user)", 
                                {"role": "client"})
    
    def test_cross_role_access(self):
        """Test that users cannot access other users' data"""
        self.print_header("TESTING CROSS-ROLE ACCESS RESTRICTIONS")
        
        # Try to access specific user data with wrong role
        # Note: These tests assume user IDs, in a real scenario you'd get actual IDs
        self.test_endpoint_access("/users/1", "GET", "client", 403, 
                                "Client: Access Other User's Profile (Should Fail)")
        self.test_endpoint_access("/users/2", "GET", "artisan", 403, 
                                "Artisan: Access Other User's Profile (Should Fail)")
    
    def print_summary(self):
        """Print test summary"""
        self.print_header("TEST SUMMARY")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"{Colors.GREEN}Passed: {passed_tests}{Colors.END}")
        print(f"{Colors.RED}Failed: {failed_tests}{Colors.END}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n{Colors.RED}Failed Tests:{Colors.END}")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  ❌ {result['test']}")
        
        print(f"\n{Colors.BOLD}Role-Based Permission System: ", end="")
        if failed_tests == 0:
            print(f"{Colors.GREEN}✅ WORKING CORRECTLY{Colors.END}")
        else:
            print(f"{Colors.RED}❌ NEEDS ATTENTION{Colors.END}")
    
    def run_all_tests(self):
        """Run the complete test suite"""
        print(f"{Colors.BOLD}{Colors.PURPLE}")
        print("🔐 STELLARTS ROLE-BASED PERMISSION TEST SUITE")
        print("=" * 50)
        print(f"{Colors.END}")
        
        # Check if API is running
        if not self.check_health():
            return
        
        # Setup test users
        self.setup_test_users()
        
        if not self.tokens:
            print(f"{Colors.RED}❌ No user tokens available. Cannot proceed with tests.{Colors.END}")
            return
        
        # Run all test categories
        self.test_public_endpoints()
        self.test_authentication_required()
        self.test_client_permissions()
        self.test_artisan_permissions()
        self.test_admin_permissions()
        self.test_cross_role_access()
        
        # Print summary
        self.print_summary()

def main():
    """Main function"""
    test_suite = RoleTestSuite()
    test_suite.run_all_tests()

if __name__ == "__main__":
    main()