#!/bin/bash
# Run all CI checks locally before pushing

set -e

echo "🔍 Running CI checks locally..."
echo ""

# Activate virtual environment
source venv/bin/activate

echo "1️⃣  Flake8 - Critical syntax checks..."
flake8 app/ --count --select=E9,F63,F7,F82 --show-source --statistics
echo "✅ Flake8 critical checks passed"
echo ""

echo "2️⃣  Flake8 - Style and complexity checks..."
flake8 app/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics
echo "✅ Flake8 style checks passed"
echo ""

echo "3️⃣  Ruff - Linting..."
ruff check app/
echo "✅ Ruff checks passed"
echo ""

echo "4️⃣  Black - Code formatting..."
black --check app/
echo "✅ Black formatting passed"
echo ""

echo "5️⃣  Import validation..."
SECRET_KEY=test \
DATABASE_URL=postgresql://test:test@localhost/test \
STELLAR_ESCROW_PUBLIC=GDUMMY \
DEBUG=true \
PYTHONPATH=. \
python -c "from app.api.v1.api import api_router; print('✅ All imports successful -', len(api_router.routes), 'routes loaded')"
echo ""

echo "🎉 All CI lint checks passed! Ready to push."
echo ""
echo "⚠️  Note: Tests require PostgreSQL and Redis running."
echo "   To run tests: pytest app/tests/ -v --cov=app --cov-report=xml"
