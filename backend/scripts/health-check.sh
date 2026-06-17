#!/bin/bash

# Health check script for Stellarts API
echo "🏥 Checking Stellarts API Health..."

API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-10}"

# Check if the API is responding
echo "📡 Testing API endpoint: $API_URL/api/v1/health"

response=$(curl -s -w "%{http_code}" -o /tmp/health_response --max-time $TIMEOUT "$API_URL/api/v1/health" 2>/dev/null)
http_code="${response: -3}"

if [ $? -eq 0 ] && [ "$http_code" = "200" ]; then
    echo "✅ API is healthy!"
    echo "📊 Response:"
    cat /tmp/health_response | python3 -m json.tool 2>/dev/null || cat /tmp/health_response
    echo ""
    
    # Test root endpoint
    echo "📡 Testing root endpoint: $API_URL/"
    curl -s "$API_URL/" | python3 -m json.tool 2>/dev/null
    echo ""
    
    echo "🎉 All endpoints are working!"
    rm -f /tmp/health_response
    exit 0
else
    echo "❌ API health check failed!"
    echo "HTTP Status Code: $http_code"
    if [ -f /tmp/health_response ]; then
        echo "Response:"
        cat /tmp/health_response
    fi
    rm -f /tmp/health_response
    exit 1
fi
