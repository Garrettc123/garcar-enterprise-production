#!/bin/bash
set -euo pipefail

# ============================================
# TEST DEPLOYMENT - Verify Everything Money
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🧪 Testing Deployment - Everything Money${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

NAMESPACE="${1:-garcar-prod}"
FAILED_TESTS=0
PASSED_TESTS=0

test_command() {
    local description="$1"
    local command="$2"

    echo -e "${YELLOW}Testing: $description${NC}"

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS: $description${NC}"
        ((PASSED_TESTS++))
        return 0
    else
        echo -e "${RED}❌ FAIL: $description${NC}"
        ((FAILED_TESTS++))
        return 1
    fi
}

echo -e "${BLUE}1. Checking Kubernetes Resources${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_command "Namespace exists" "kubectl get namespace $NAMESPACE"
test_command "PostgreSQL pod is running" "kubectl get pod -l app=postgres -n $NAMESPACE | grep Running"
test_command "API Gateway deployment exists" "kubectl get deployment api-gateway -n $NAMESPACE"
test_command "Revenue Aggregator deployment exists" "kubectl get deployment revenue-aggregator -n $NAMESPACE"
test_command "AI Agent Hub deployment exists" "kubectl get deployment ai-agent-hub -n $NAMESPACE"

echo ""
echo -e "${BLUE}2. Checking Services${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_command "API Gateway service exists" "kubectl get service api-gateway -n $NAMESPACE"
test_command "Revenue Aggregator service exists" "kubectl get service revenue-aggregator-service -n $NAMESPACE"
test_command "AI Agent Hub service exists" "kubectl get service ai-agent-hub-service -n $NAMESPACE"
test_command "PostgreSQL service exists" "kubectl get service postgres -n $NAMESPACE"

echo ""
echo -e "${BLUE}3. Health Check Endpoints${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -e "${YELLOW}Testing: API Gateway health endpoint${NC}"
if kubectl exec -n $NAMESPACE deploy/api-gateway -- curl -f http://localhost:5000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: API Gateway health endpoint${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}❌ FAIL: API Gateway health endpoint${NC}"
    ((FAILED_TESTS++))
fi

echo -e "${YELLOW}Testing: Revenue Aggregator health endpoint${NC}"
if kubectl exec -n $NAMESPACE deploy/revenue-aggregator -- curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Revenue Aggregator health endpoint${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}❌ FAIL: Revenue Aggregator health endpoint${NC}"
    ((FAILED_TESTS++))
fi

echo -e "${YELLOW}Testing: AI Agent Hub health endpoint${NC}"
if kubectl exec -n $NAMESPACE deploy/ai-agent-hub -- curl -f http://localhost:8081/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: AI Agent Hub health endpoint${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}❌ FAIL: AI Agent Hub health endpoint${NC}"
    ((FAILED_TESTS++))
fi

echo ""
echo -e "${BLUE}4. Database Connectivity${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -e "${YELLOW}Testing: PostgreSQL connection${NC}"
if kubectl exec -n $NAMESPACE deploy/postgres -- psql -U postgres -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: PostgreSQL connection${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}❌ FAIL: PostgreSQL connection${NC}"
    ((FAILED_TESTS++))
fi

echo -e "${YELLOW}Testing: Database tables exist${NC}"
if kubectl exec -n $NAMESPACE deploy/postgres -- psql -U postgres -d revenue_aggregator -c "\dt" 2>&1 | grep -q "systems"; then
    echo -e "${GREEN}✅ PASS: Database tables exist${NC}"
    ((PASSED_TESTS++))
else
    echo -e "${RED}❌ FAIL: Database tables exist${NC}"
    ((FAILED_TESTS++))
fi

echo ""
echo -e "${BLUE}5. Deployment Readiness${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_command "API Gateway deployment is ready" "kubectl get deployment api-gateway -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}' | grep True"
test_command "Revenue Aggregator deployment is ready" "kubectl get deployment revenue-aggregator -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}' | grep True"
test_command "AI Agent Hub deployment is ready" "kubectl get deployment ai-agent-hub -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type==\"Available\")].status}' | grep True"

echo ""
echo -e "${BLUE}6. Pod Status${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -e "${YELLOW}Current pods:${NC}"
kubectl get pods -n $NAMESPACE

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Test Results${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}✅ Passed: $PASSED_TESTS${NC}"
echo -e "${RED}❌ Failed: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║   🎉 ALL TESTS PASSED! DEPLOYMENT SUCCESSFUL! 🎉           ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}💰 All revenue systems are operational and ready to generate money!${NC}"
    exit 0
else
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                                                              ║${NC}"
    echo -e "${RED}║   ⚠️  SOME TESTS FAILED - CHECK LOGS                       ║${NC}"
    echo -e "${RED}║                                                              ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting tips:${NC}"
    echo "  1. Check pod logs: kubectl logs -f deployment/[service-name] -n $NAMESPACE"
    echo "  2. Describe failing pods: kubectl describe pod [pod-name] -n $NAMESPACE"
    echo "  3. Check events: kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp'"
    exit 1
fi
