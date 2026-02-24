#!/bin/bash

# Test setup script for Stellarts backend
echo "🚀 Testing Stellarts Backend Setup..."

# Check if required files exist
echo "📁 Checking project structure..."

required_files=(
    "app/main.py"
    "app/core/config.py" 
    "app/api/v1/endpoints/health.py"
    "requirements.txt"
    "Dockerfile"
    "docker-compose.yml"
    "Makefile"
    ".env.example"
    ".github/workflows/ci.yml"
    "README.md"
)

missing_files=()
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        missing_files+=("$file")
    fi
done

if [ ${#missing_files[@]} -eq 0 ]; then
    echo "✅ All required files are present"
else
    echo "❌ Missing files:"
    printf '%s\n' "${missing_files[@]}"
    exit 1
fi

# Check if .env.example exists and create .env if needed
if [ ! -f ".env" ]; then
    echo "📋 Creating .env from template..."
    cp .env.example .env
    echo "✅ .env file created"
fi

# Test Python syntax
echo "🐍 Testing Python syntax..."
python3 -m py_compile app/main.py
if [ $? -eq 0 ]; then
    echo "✅ Python syntax is valid"
else
    echo "❌ Python syntax errors found"
    exit 1
fi

# Check if Docker is available
echo "🐳 Checking Docker availability..."
if command -v docker &> /dev/null; then
    echo "✅ Docker is available"
    
    # Test Docker build if Docker is running
    if docker info &> /dev/null; then
        echo "🔨 Testing Docker build..."
        docker build -t stellarts-test . --quiet
        if [ $? -eq 0 ]; then
            echo "✅ Docker build successful"
            docker rmi stellarts-test --force &> /dev/null
        else
            echo "❌ Docker build failed"
            exit 1
        fi
    else
        echo "⚠️  Docker daemon is not running (this is okay for setup verification)"
    fi
else
    echo "⚠️  Docker is not installed (required for running the application)"
fi

echo ""
echo "🎉 Stellarts backend setup verification complete!"
echo ""
echo "To start the application:"
echo "1. Make sure Docker is running"
echo "2. Run: make up"
echo "3. Visit: http://localhost:8000/api/v1/health"
echo ""
echo "For development:"
echo "- View logs: make logs"
echo "- Run tests: make test"
echo "- Access shell: make shell"
echo "- Format code: make format"
