#!/bin/bash
# Quick CI checks before pushing

set -e

echo "🔍 Running flake8 syntax checks..."
./venv/bin/flake8 app/ --count --select=E9,F63,F7,F82 --show-source --statistics

echo ""
echo "✅ All critical checks passed!"
echo ""
echo "ℹ️  To run full flake8 (with style warnings):"
echo "   ./venv/bin/flake8 app/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics"
