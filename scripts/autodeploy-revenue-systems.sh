#!/bin/bash
set -euo pipefail

# ============================================
# GARCAR ENTERPRISE AUTO-DEPLOY
# Deploy all revenue systems in parallel
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo -e "${MAGENTA}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║     GARCAR ENTERPRISE AUTO-DEPLOYMENT SYSTEM             ║
║     Deploy All Revenue Systems in Under 5 Minutes        ║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check prerequisites
echo -e "${BLUE}🔍 Checking prerequisites...${NC}"
PREREQ_PASS=true

for cmd in docker kubectl git curl; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}❌ $cmd not found${NC}"
        PREREQ_PASS=false
    else
        echo -e "${GREEN}✅ $cmd${NC}"
    fi
done

if [ "$PREREQ_PASS" = false ]; then
    echo -e "${RED}Install missing prerequisites and try again${NC}"
    exit 1
fi

# Configuration
GITHUB_USER="Garrettc123"
DEPLOY_METHOD="${1:-railway}"  # railway, vercel, or kubernetes
REGION="${2:-us-east-1}"

echo ""
echo -e "${BLUE}📋 Deployment Configuration:${NC}"
echo "  Method: $DEPLOY_METHOD"
echo "  Region: $REGION"
echo "  GitHub: $GITHUB_USER"
echo ""

# Create deployment directory
DEPLOY_DIR="$HOME/.garcar-deploy"
mkdir -p $DEPLOY_DIR/logs
cd $DEPLOY_DIR

echo -e "${YELLOW}📦 Cloning revenue repositories...${NC}"

# Revenue systems to deploy
declare -A REPOS=(
    ["smart-contract-auditor-ai"]="8000"
    ["lead-enrichment-engine"]="8001"
    ["customer-churn-predictor"]="8002"
    ["defi-yield-aggregator"]="8003"
)

# Clone repositories in parallel
for repo in "${!REPOS[@]}"; do
    (
        if [ ! -d "$repo" ]; then
            echo -e "${BLUE}📥 Cloning $repo...${NC}"
            git clone https://github.com/$GITHUB_USER/$repo.git 2>&1 | tee $DEPLOY_DIR/logs/${repo}_clone.log
        else
            echo -e "${YELLOW}🔄 Updating $repo...${NC}"
            cd $repo && git pull origin main 2>&1 | tee $DEPLOY_DIR/logs/${repo}_update.log
        fi
    ) &
done
wait

echo -e "${GREEN}✅ All repositories ready${NC}"
echo ""

# Deploy based on method
if [ "$DEPLOY_METHOD" = "railway" ]; then
    echo -e "${MAGENTA}🚂 Deploying to Railway...${NC}"
    
    # Check Railway CLI
    if ! command -v railway &> /dev/null; then
        echo -e "${YELLOW}📦 Installing Railway CLI...${NC}"
        curl -fsSL https://railway.app/install.sh | sh
        export PATH="$HOME/.railway/bin:$PATH"
    fi
    
    # Deploy each service
    for repo in "${!REPOS[@]}"; do
        port="${REPOS[$repo]}"
        (
            echo -e "${BLUE}🚀 Deploying $repo on port $port...${NC}"
            cd $DEPLOY_DIR/$repo
            
            # Initialize Railway project if needed
            if [ ! -f ".railway/config.json" ]; then
                railway init --name "$repo"
            fi
            
            # Set environment variables
            railway variables set PORT="$port"
            railway variables set NODE_ENV=production
            
            # Deploy
            railway up 2>&1 | tee $DEPLOY_DIR/logs/${repo}_deploy.log
            
            # Get deployment URL
            URL=$(railway status --json | jq -r '.deployments[0].url')
            echo -e "${GREEN}✅ $repo deployed: $URL${NC}"
            echo "$repo,$URL,$port" >> $DEPLOY_DIR/deployments.csv
            
        ) &
    done
    wait
    
elif [ "$DEPLOY_METHOD" = "vercel" ]; then
    echo -e "${MAGENTA}▲ Deploying to Vercel...${NC}"
    
    # Check Vercel CLI
    if ! command -v vercel &> /dev/null; then
        echo -e "${YELLOW}📦 Installing Vercel CLI...${NC}"
        npm i -g vercel
    fi
    
    for repo in "${!REPOS[@]}"; do
        (
            echo -e "${BLUE}🚀 Deploying $repo...${NC}"
            cd $DEPLOY_DIR/$repo
            vercel --prod --yes 2>&1 | tee $DEPLOY_DIR/logs/${repo}_deploy.log
        ) &
    done
    wait
    
elif [ "$DEPLOY_METHOD" = "kubernetes" ]; then
    echo -e "${MAGENTA}☸️  Deploying to Kubernetes...${NC}"
    
    # Create namespace
    kubectl create namespace garcar-revenue || true
    
    for repo in "${!REPOS[@]}"; do
        port="${REPOS[$repo]}"
        (
            echo -e "${BLUE}🚀 Deploying $repo...${NC}"
            cd $DEPLOY_DIR/$repo
            
            # Build Docker image
            docker build -t "$repo:latest" .
            
            # Create Kubernetes deployment
            cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $repo
  namespace: garcar-revenue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: $repo
  template:
    metadata:
      labels:
        app: $repo
    spec:
      containers:
      - name: $repo
        image: $repo:latest
        ports:
        - containerPort: $port
        env:
        - name: PORT
          value: "$port"
        - name: NODE_ENV
          value: "production"
---
apiVersion: v1
kind: Service
metadata:
  name: $repo
  namespace: garcar-revenue
spec:
  selector:
    app: $repo
  ports:
  - port: 80
    targetPort: $port
  type: LoadBalancer
EOF
            
            echo -e "${GREEN}✅ $repo deployed to Kubernetes${NC}"
        ) &
    done
    wait
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          🎉 DEPLOYMENT COMPLETE!                         ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📊 Deployed Services:${NC}"
if [ -f "$DEPLOY_DIR/deployments.csv" ]; then
    column -t -s',' $DEPLOY_DIR/deployments.csv
fi

echo ""
echo -e "${YELLOW}📈 Next Steps:${NC}"
echo "1. Configure Stripe webhooks for payment processing"
echo "2. Set up domain DNS records for custom URLs"
echo "3. Enable SSL certificates"
echo "4. Configure monitoring alerts"
echo "5. Start customer acquisition!"
echo ""

echo -e "${BLUE}📁 Deployment logs: $DEPLOY_DIR/logs/${NC}"
echo -e "${BLUE}🔗 Service URLs saved to: $DEPLOY_DIR/deployments.csv${NC}"
echo ""

echo -e "${GREEN}💰 Revenue systems are now LIVE and ready to generate cash!${NC}"
echo ""
