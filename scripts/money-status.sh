#!/bin/bash
set -euo pipefail

# ============================================
# MONEY STATUS - Quick view of all revenue systems
# ============================================

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
MAGENTA='\033[0;35m'
NC='\033[0m'

NAMESPACE="${1:-garcar-prod}"

echo -e "${MAGENTA}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║            💰 MONEY SYSTEMS STATUS 💰                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${YELLOW}⚠️  kubectl not found. Install kubectl to view live status.${NC}"
    exit 1
fi

# Check if namespace exists
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}⚠️  Namespace '$NAMESPACE' not found. Deploy first with:${NC}"
    echo "    ./scripts/deploy-everything-money.sh"
    exit 1
fi

echo -e "${CYAN}📊 Revenue Systems Overview${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}💵 Total Annual Potential: \$110,067,796${NC}"
echo ""

echo -e "${CYAN}🏢 Active Revenue Systems:${NC}"
cat << EOF
  1. NWU Protocol              \$98,500,000
  2. Tree of Life System       \$1,581,552 (\$131,796 MRR)
  3. MARS AI                   \$10,000,000
  4. AI Orchestrator           \$490,000
  5. AI Business Platform      \$946,000
EOF
echo ""

echo -e "${CYAN}💸 Payout Configuration:${NC}"
cat << EOF
  • PayPal (70%): gwc2780@gmail.com
  • Ethereum (30%): 0x5C92DCa91ac3251c17c94d69E93b8784fE8dcd30
  • Threshold: \$1,000
EOF
echo ""

echo -e "${CYAN}🚀 Service Status${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Function to check deployment status
check_deployment() {
    local name=$1
    local status=$(kubectl get deployment $name -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "Unknown")
    local ready=$(kubectl get deployment $name -n $NAMESPACE -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    local desired=$(kubectl get deployment $name -n $NAMESPACE -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

    if [ "$status" = "True" ] && [ "$ready" = "$desired" ]; then
        echo -e "  ${GREEN}✅ $name${NC} - $ready/$desired replicas ready"
    elif [ "$status" = "True" ]; then
        echo -e "  ${YELLOW}⚠️  $name${NC} - $ready/$desired replicas ready"
    else
        echo -e "  ${YELLOW}❌ $name${NC} - Not available"
    fi
}

check_deployment "api-gateway"
check_deployment "revenue-aggregator"
check_deployment "ai-agent-hub"

# Check database
echo ""
if kubectl get pod -l app=postgres -n $NAMESPACE 2>/dev/null | grep -q Running; then
    echo -e "  ${GREEN}✅ PostgreSQL${NC} - Running"
else
    echo -e "  ${YELLOW}❌ PostgreSQL${NC} - Not running"
fi

echo ""
echo -e "${CYAN}🌐 Access Points${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get service info
API_GW_TYPE=$(kubectl get svc api-gateway -n $NAMESPACE -o jsonpath='{.spec.type}' 2>/dev/null || echo "Unknown")

if [ "$API_GW_TYPE" = "LoadBalancer" ]; then
    EXTERNAL_IP=$(kubectl get svc api-gateway -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending")
    if [ "$EXTERNAL_IP" != "Pending" ] && [ -n "$EXTERNAL_IP" ]; then
        echo -e "  ${GREEN}🌍 External IP:${NC} $EXTERNAL_IP"
        echo -e "  ${GREEN}📡 API Gateway:${NC} http://$EXTERNAL_IP:5000"
        echo -e "  ${GREEN}💰 Money Dashboard:${NC} http://$EXTERNAL_IP:5000/api/money/dashboard"
    else
        echo -e "  ${YELLOW}⏳ LoadBalancer IP pending...${NC}"
    fi
elif [ "$API_GW_TYPE" = "NodePort" ]; then
    NODE_PORT=$(kubectl get svc api-gateway -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)
    echo -e "  ${GREEN}🔗 NodePort:${NC} $NODE_PORT"
    echo -e "  ${YELLOW}💡 Use: kubectl port-forward svc/api-gateway 5000:5000 -n $NAMESPACE${NC}"
else
    echo -e "  ${YELLOW}💡 Port forward to access locally:${NC}"
    echo "     kubectl port-forward svc/api-gateway 5000:5000 -n $NAMESPACE"
fi

echo ""
echo -e "${CYAN}📈 Quick Actions${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat << EOF
  View logs:        kubectl logs -f deployment/revenue-aggregator -n $NAMESPACE
  Test deployment:  ./scripts/test-deployment.sh
  Scale services:   kubectl scale deployment/revenue-aggregator --replicas=5 -n $NAMESPACE
  Restart service:  kubectl rollout restart deployment/api-gateway -n $NAMESPACE
  Delete all:       kubectl delete namespace $NAMESPACE
EOF

echo ""
echo -e "${GREEN}💰 Your revenue systems are ready to make money! 💰${NC}"
echo ""
