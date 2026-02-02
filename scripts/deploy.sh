#!/bin/bash
set -euo pipefail

echo "🚀 Garcar Enterprise Production Deployment"
echo "============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
command -v kubectl >/dev/null 2>&1 || { echo -e "${RED}❌ kubectl required${NC}"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}❌ docker required${NC}"; exit 1; }

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Create namespace
echo "📦 Creating namespace..."
kubectl apply -f k8s/production/namespace.yaml

# Apply secrets (ensure they're configured)
echo "🔐 Applying secrets..."
if [ -f "k8s/production/secrets-encrypted.yaml" ]; then
    kubectl apply -f k8s/production/secrets-encrypted.yaml
else
    echo -e "${YELLOW}⚠️  WARNING: Using template secrets. Update with actual values!${NC}"
    kubectl apply -f k8s/production/secrets.yaml
fi

# Apply ConfigMaps
echo "⚙️  Applying configuration..."
kubectl apply -f k8s/production/configmap.yaml

# Deploy PostgreSQL
echo "💾 Deploying PostgreSQL..."
kubectl apply -f k8s/production/postgres.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n garcar-prod --timeout=300s

# Initialize database
echo "🗄️ Initializing database..."
kubectl exec -i deploy/postgres -n garcar-prod -- psql -U postgres < database/schema.sql || echo "Schema may already exist"

# Deploy services
echo "🚀 Deploying services..."
kubectl apply -f k8s/production/revenue-aggregator.yaml
kubectl apply -f k8s/production/ai-agent-hub.yaml
kubectl apply -f k8s/production/api-gateway.yaml

# Deploy ingress
echo "🌐 Configuring ingress..."
kubectl apply -f k8s/production/ingress.yaml

# Wait for deployments
echo "⏳ Waiting for deployments to be ready..."
kubectl rollout status deployment/revenue-aggregator -n garcar-prod --timeout=300s
kubectl rollout status deployment/ai-agent-hub -n garcar-prod --timeout=300s
kubectl rollout status deployment/api-gateway -n garcar-prod --timeout=300s

echo ""
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo ""
echo "============================================="
echo "📊 Service Status:"
kubectl get pods -n garcar-prod
echo ""
echo "🌐 Service URLs:"
kubectl get svc -n garcar-prod
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo "View logs: kubectl logs -f deployment/revenue-aggregator -n garcar-prod"
