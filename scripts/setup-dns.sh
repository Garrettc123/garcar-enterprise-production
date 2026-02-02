#!/bin/bash

# DNS Configuration Script
# Helps setup DNS records for all services

set -e

echo "🌐 GARCAR Enterprise - DNS Setup"
echo "=============================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load domain configuration
if [ -f ".domains.env" ]; then
    source .domains.env
else
    # Default domains
    API_DOMAIN="api.garcar-enterprise.com"
    REVENUE_DOMAIN="revenue.garcar-enterprise.com"
    AGENTS_DOMAIN="agents.garcar-enterprise.com"
    MONITORING_DOMAIN="monitoring.garcar-enterprise.com"
    PROMETHEUS_DOMAIN="prometheus.garcar-enterprise.com"
fi

echo "Configured domains:"
echo "  - $API_DOMAIN"
echo "  - $REVENUE_DOMAIN"
echo "  - $AGENTS_DOMAIN"
echo "  - $MONITORING_DOMAIN"
echo "  - $PROMETHEUS_DOMAIN"
echo ""

# Get LoadBalancer IP from Kubernetes
echo "🔍 Fetching LoadBalancer IP from Kubernetes..."
echo ""

if ! command -v kubectl &> /dev/null; then
    echo -e "${YELLOW}⚠️  kubectl not found. Please install kubectl first.${NC}"
    echo "Visit: https://kubernetes.io/docs/tasks/tools/"
    echo ""
    read -p "Enter LoadBalancer IP manually: " LOADBALANCER_IP
else
    # Try to get LoadBalancer IP
    LOADBALANCER_IP=$(kubectl get svc -n garcar-prod api-gateway-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    
    if [ -z "$LOADBALANCER_IP" ]; then
        # Try hostname instead
        LOADBALANCER_IP=$(kubectl get svc -n garcar-prod api-gateway-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
    fi
    
    if [ -z "$LOADBALANCER_IP" ]; then
        echo -e "${YELLOW}⚠️  Could not retrieve LoadBalancer IP automatically${NC}"
        echo "Make sure your Kubernetes cluster is running and services are deployed"
        echo ""
        read -p "Enter LoadBalancer IP manually: " LOADBALANCER_IP
    else
        echo -e "${GREEN}✅ LoadBalancer IP: $LOADBALANCER_IP${NC}"
    fi
fi

if [ -z "$LOADBALANCER_IP" ]; then
    echo -e "${RED}❌ No LoadBalancer IP provided. Cannot continue.${NC}"
    exit 1
fi

echo ""
echo "LoadBalancer IP/Hostname: $LOADBALANCER_IP"
echo ""

# Determine if IP or hostname
if [[ $LOADBALANCER_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    RECORD_TYPE="A"
    echo "Record type: A (IPv4 address)"
else
    RECORD_TYPE="CNAME"
    echo "Record type: CNAME (hostname)"
fi

echo ""
echo "========================================"
echo "📝 DNS Records Configuration"
echo "========================================"
echo ""
echo "Add the following DNS records to your domain registrar:"
echo ""

# Generate DNS records
if [ "$RECORD_TYPE" == "A" ]; then
    cat << EOF
╭──────────────────────────────────────────────────╮
│ Record Type: A                                        │
├──────────────────────────────────────────────────┤
│ Name                      │ Value                   │
├──────────────────────────────────────────────────┤
│ $API_DOMAIN       │ $LOADBALANCER_IP        │
│ $REVENUE_DOMAIN   │ $LOADBALANCER_IP        │
│ $AGENTS_DOMAIN    │ $LOADBALANCER_IP        │
│ $MONITORING_DOMAIN│ $LOADBALANCER_IP        │
│ $PROMETHEUS_DOMAIN│ $LOADBALANCER_IP        │
╰──────────────────────────────────────────────────╯

TTL: 300 (5 minutes) - can increase to 3600 (1 hour) after testing

EOF
else
    cat << EOF
╭──────────────────────────────────────────────────╮
│ Record Type: CNAME                                     │
├──────────────────────────────────────────────────┤
│ Name                      │ Value                   │
├──────────────────────────────────────────────────┤
│ $API_DOMAIN       │ $LOADBALANCER_IP        │
│ $REVENUE_DOMAIN   │ $LOADBALANCER_IP        │
│ $AGENTS_DOMAIN    │ $LOADBALANCER_IP        │
│ $MONITORING_DOMAIN│ $LOADBALANCER_IP        │
│ $PROMETHEUS_DOMAIN│ $LOADBALANCER_IP        │
╰──────────────────────────────────────────────────╯

TTL: 300 (5 minutes) - can increase to 3600 (1 hour) after testing

EOF
fi

echo ""
echo "📝 Instructions by DNS Provider:"
echo ""
echo "Cloudflare:"
echo "  1. Log in to Cloudflare dashboard"
echo "  2. Select your domain"
echo "  3. Go to DNS > Records"
echo "  4. Click 'Add record'"
echo "  5. Add each record as shown above"
echo "  6. Set Proxy status to 'Proxied' (orange cloud) for HTTPS"
echo ""
echo "AWS Route53:"
echo "  1. Open Route53 console"
echo "  2. Select your hosted zone"
echo "  3. Click 'Create record'"
echo "  4. Add each record as shown above"
echo "  5. Use 'Simple routing' policy"
echo ""
echo "Google Cloud DNS:"
echo "  1. Open Cloud DNS console"
echo "  2. Select your zone"
echo "  3. Click 'Add record set'"
echo "  4. Add each record as shown above"
echo ""
echo "Namecheap/GoDaddy/Other:"
echo "  1. Log in to your domain registrar"
echo "  2. Find DNS management/Advanced DNS"
echo "  3. Add/edit records as shown above"
echo ""

echo "========================================"
echo "✅ DNS Verification"
echo "========================================"
echo ""
echo "After adding DNS records, verify them with:"
echo ""
echo "  dig $API_DOMAIN"
echo "  nslookup $API_DOMAIN"
echo ""
echo "Or use online tools:"
echo "  - https://dnschecker.org"
echo "  - https://mxtoolbox.com/SuperTool.aspx"
echo ""

read -p "Press Enter after you've configured DNS records..."

echo ""
echo "🔍 Testing DNS resolution..."
echo ""

for domain in "$API_DOMAIN" "$REVENUE_DOMAIN" "$AGENTS_DOMAIN"; do
    echo -n "Testing $domain... "
    if host "$domain" > /dev/null 2>&1; then
        RESOLVED_IP=$(host "$domain" | grep "has address" | awk '{print $4}' | head -1)
        echo -e "${GREEN}✅ Resolved to: $RESOLVED_IP${NC}"
    else
        echo -e "${YELLOW}⚠️  Not resolved yet (DNS propagation can take 5-60 minutes)${NC}"
    fi
done

echo ""
echo "🎉 DNS setup complete!"
echo ""
echo "Next steps:"
echo "1. Wait for DNS propagation (5-60 minutes)"
echo "2. Verify SSL certificates: kubectl get certificates -n garcar-prod"
echo "3. Test endpoints: curl https://$API_DOMAIN/health"
echo "4. Setup monitoring alerts: ./scripts/setup-monitoring.sh"
echo ""

# Save configuration
cat > ".dns-config.env" << EOF
LOADBALANCER_IP=$LOADBALANCER_IP
RECORD_TYPE=$RECORD_TYPE
CONFIGURED_DATE=$(date)
EOF

echo "Configuration saved to .dns-config.env"
echo ""
