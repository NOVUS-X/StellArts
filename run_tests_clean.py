import sys
import os

# Remove problematic paths
print("Original path:", sys.path)
sys.path = [p for p in sys.path if "python3.10" not in p]
print("Cleaned path:", sys.path)

os.environ["SECRET_KEY"] = "supersecret"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
sys.exit(pytest.main(["-v", "backend/app/tests/test_crud_endpoints.py", "backend/app/tests/test_geolocation_api.py"]))
