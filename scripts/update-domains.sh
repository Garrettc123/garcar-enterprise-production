#!/bin/bash

# Domain Configuration Script
# Updates all domain references in Kubernetes manifests

set -e

echo "🌐 GARCAR Enterprise - Domain Configuration"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Current domains (default placeholders)
CURRENT_DOMAINS=(
    "api.garcar-enterprise.com"
    "revenue.garcar-enterprise.com"
    "agents.garcar-enterprise.com"
    "monitoring.garcar-enterprise.com"
    "prometheus.garcar-enterprise.com"
)

echo "Current domains:"
for domain in "${CURRENT_DOMAINS[@]}"; do
    echo "  - $domain"
done
echo ""

read -p "Do you want to update these domains? (y/n): " update_domains

if [[ "$update_domains" != "y" && "$update_domains" != "Y" ]]; then
    echo "Domain configuration skipped."
    exit 0
fi

echo ""
echo "Enter your custom domains (press Enter to keep default):"
echo ""

# Prompt for new domains
read -p "API Gateway domain [${CURRENT_DOMAINS[0]}]: " NEW_API_DOMAIN
NEW_API_DOMAIN=${NEW_API_DOMAIN:-${CURRENT_DOMAINS[0]}}

read -p "Revenue service domain [${CURRENT_DOMAINS[1]}]: " NEW_REVENUE_DOMAIN
NEW_REVENUE_DOMAIN=${NEW_REVENUE_DOMAIN:-${CURRENT_DOMAINS[1]}}

read -p "AI Agents domain [${CURRENT_DOMAINS[2]}]: " NEW_AGENTS_DOMAIN
NEW_AGENTS_DOMAIN=${NEW_AGENTS_DOMAIN:-${CURRENT_DOMAINS[2]}}

read -p "Monitoring (Grafana) domain [${CURRENT_DOMAINS[3]}]: " NEW_MONITORING_DOMAIN
NEW_MONITORING_DOMAIN=${NEW_MONITORING_DOMAIN:-${CURRENT_DOMAINS[3]}}

read -p "Prometheus domain [${CURRENT_DOMAINS[4]}]: " NEW_PROMETHEUS_DOMAIN
NEW_PROMETHEUS_DOMAIN=${NEW_PROMETHEUS_DOMAIN:-${CURRENT_DOMAINS[4]}}

echo ""
echo "New domain configuration:"
echo "  API Gateway: $NEW_API_DOMAIN"
echo "  Revenue: $NEW_REVENUE_DOMAIN"
echo "  AI Agents: $NEW_AGENTS_DOMAIN"
echo "  Monitoring: $NEW_MONITORING_DOMAIN"
echo "  Prometheus: $NEW_PROMETHEUS_DOMAIN"
echo ""

read -p "Confirm and update? (y/n): " confirm

if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Update cancelled."
    exit 0
fi

echo ""
echo "🔧 Updating configuration files..."

# Update ingress.yaml
INGRESS_FILE="k8s/production/ingress.yaml"
if [ -f "$INGRESS_FILE" ]; then
    echo "Updating $INGRESS_FILE..."
    
    # Create backup
    cp "$INGRESS_FILE" "${INGRESS_FILE}.backup"
    
    # Update domains
    sed -i.tmp "s|${CURRENT_DOMAINS[0]}|$NEW_API_DOMAIN|g" "$INGRESS_FILE"
    sed -i.tmp "s|${CURRENT_DOMAINS[1]}|$NEW_REVENUE_DOMAIN|g" "$INGRESS_FILE"
    sed -i.tmp "s|${CURRENT_DOMAINS[2]}|$NEW_AGENTS_DOMAIN|g" "$INGRESS_FILE"
    rm -f "${INGRESS_FILE}.tmp"
    
    echo -e "${GREEN}✅ Ingress updated${NC}"
else
    echo -e "${YELLOW}⚠️  $INGRESS_FILE not found${NC}"
fi

# Update monitoring ingress if exists
MONITORING_INGRESS="k8s/production/monitoring-ingress.yaml"
if [ -f "$MONITORING_INGRESS" ]; then
    echo "Updating $MONITORING_INGRESS..."
    cp "$MONITORING_INGRESS" "${MONITORING_INGRESS}.backup"
    sed -i.tmp "s|${CURRENT_DOMAINS[3]}|$NEW_MONITORING_DOMAIN|g" "$MONITORING_INGRESS"
    sed -i.tmp "s|${CURRENT_DOMAINS[4]}|$NEW_PROMETHEUS_DOMAIN|g" "$MONITORING_INGRESS"
    rm -f "${MONITORING_INGRESS}.tmp"
    echo -e "${GREEN}✅ Monitoring ingress updated${NC}"
fi

# Update README.md references
if [ -f "README.md" ]; then
    echo "Updating README.md..."
    cp "README.md" "README.md.backup"
    sed -i.tmp "s|${CURRENT_DOMAINS[0]}|$NEW_API_DOMAIN|g" "README.md"
    sed -i.tmp "s|${CURRENT_DOMAINS[1]}|$NEW_REVENUE_DOMAIN|g" "README.md"
    sed -i.tmp "s|${CURRENT_DOMAINS[2]}|$NEW_AGENTS_DOMAIN|g" "README.md"
    sed -i.tmp "s|${CURRENT_DOMAINS[3]}|$NEW_MONITORING_DOMAIN|g" "README.md"
    sed -i.tmp "s|${CURRENT_DOMAINS[4]}|$NEW_PROMETHEUS_DOMAIN|g" "README.md"
    rm -f "README.md.tmp"
    echo -e "${GREEN}✅ README updated${NC}"
fi

echo ""
echo -e "${GREEN}✅ Domain configuration complete!${NC}"
echo ""
echo "Updated files:"
echo "  - k8s/production/ingress.yaml"
echo "  - k8s/production/monitoring-ingress.yaml (if exists)"
echo "  - README.md"
echo ""
echo "Backup files created with .backup extension"
echo ""
echo "Next steps:"
echo "1. Review changes: git diff"
echo "2. Commit changes: git add . && git commit -m 'Update domain configuration'"
echo "3. Push to GitHub: git push origin main"
echo "4. Configure DNS records: ./scripts/setup-dns.sh"
echo ""

# Save domain configuration for DNS script
cat > ".domains.env" << EOF
API_DOMAIN=$NEW_API_DOMAIN
REVENUE_DOMAIN=$NEW_REVENUE_DOMAIN
AGENTS_DOMAIN=$NEW_AGENTS_DOMAIN
MONITORING_DOMAIN=$NEW_MONITORING_DOMAIN
PROMETHEUS_DOMAIN=$NEW_PROMETHEUS_DOMAIN
EOF

echo "Domain configuration saved to .domains.env"
echo ""
