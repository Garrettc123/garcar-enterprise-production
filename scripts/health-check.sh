#!/bin/bash
set -euo pipefail

echo "🏥 Garcar Enterprise Health Check"
echo "===================================="
echo ""

API_GATEWAY=${API_GATEWAY_URL:-http://localhost:5000}
REVENUE_SERVICE=${REVENUE_URL:-http://localhost:8080}
AGENT_HUB=${AGENT_URL:-http://localhost:8081}

# Function to check service
check_service() {
    local name=$1
    local url=$2
    local endpoint=$3
    
    echo -n "Checking $name... "
    
    if curl -sf "$url$endpoint" > /dev/null; then
        echo "✅ Healthy"
        return 0
    else
        echo "❌ Unhealthy"
        return 1
    fi
}

# Check all services
FAILURES=0

check_service "API Gateway" "$API_GATEWAY" "/health" || ((FAILURES++))
check_service "Revenue Aggregator" "$REVENUE_SERVICE" "/health" || ((FAILURES++))
check_service "AI Agent Hub" "$AGENT_HUB" "/status" || ((FAILURES++))

echo ""
echo "===================================="

if [ $FAILURES -eq 0 ]; then
    echo "✅ All services healthy"
    exit 0
else
    echo "❌ $FAILURES service(s) unhealthy"
    exit 1
fi
