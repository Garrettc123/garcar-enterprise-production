#!/bin/bash

# GitHub Secrets Configuration Script
# Run this script to generate and configure all required secrets

set -e

echo "🔐 GARCAR Enterprise - GitHub Secrets Configuration"
echo "================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Repository details
REPO_OWNER="Garrettc123"
REPO_NAME="garcar-enterprise-production"

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) is not installed${NC}"
    echo "Install it from: https://cli.github.com/"
    echo "Or use: brew install gh (macOS) or apt install gh (Linux)"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not authenticated with GitHub CLI${NC}"
    echo "Running: gh auth login"
    gh auth login
fi

echo -e "${GREEN}✅ GitHub CLI authenticated${NC}"
echo ""

# Function to generate random secret
generate_secret() {
    openssl rand -base64 $1 2>/dev/null || head -c $1 /dev/urandom | base64
}

# Generate all secrets
echo "🔑 Generating secrets..."
echo ""

JWT_SECRET=$(generate_secret 32)
DB_PASSWORD=$(generate_secret 24)
REDIS_PASSWORD=$(generate_secret 24)
GRAFANA_PASSWORD=$(generate_secret 16)

echo -e "${GREEN}✅ Secrets generated${NC}"
echo ""

# Display generated secrets
echo "📋 Generated Secrets (SAVE THESE SECURELY!):"
echo "==========================================="
echo ""
echo "JWT_SECRET: $JWT_SECRET"
echo "DB_PASSWORD: $DB_PASSWORD"
echo "REDIS_PASSWORD: $REDIS_PASSWORD"
echo "GRAFANA_PASSWORD: $GRAFANA_PASSWORD"
echo ""

# Save to local file (encrypted)
SECRETS_FILE=".secrets.env"
cat > "$SECRETS_FILE" << EOF
# GARCAR Enterprise Secrets
# Generated on $(date)
# KEEP THIS FILE SECURE - DO NOT COMMIT TO GIT

JWT_SECRET=$JWT_SECRET
DB_PASSWORD=$DB_PASSWORD
REDIS_PASSWORD=$REDIS_PASSWORD
GRAFANA_PASSWORD=$GRAFANA_PASSWORD
EOF

echo -e "${GREEN}✅ Secrets saved to $SECRETS_FILE${NC}"
echo ""

# Check for kubeconfig
if [ -f "$HOME/.kube/config" ]; then
    echo "🔍 Found kubeconfig at $HOME/.kube/config"
    KUBECONFIG_BASE64=$(cat "$HOME/.kube/config" | base64 -w 0 2>/dev/null || cat "$HOME/.kube/config" | base64)
    echo "KUBECONFIG_BASE64=$KUBECONFIG_BASE64" >> "$SECRETS_FILE"
    echo -e "${GREEN}✅ Kubeconfig encoded${NC}"
else
    echo -e "${YELLOW}⚠️  Kubeconfig not found at $HOME/.kube/config${NC}"
    echo "You'll need to add KUBECONFIG manually"
fi
echo ""

# Prompt for AWS credentials (optional)
read -p "Configure AWS for backups? (y/n): " configure_aws
if [[ "$configure_aws" == "y" || "$configure_aws" == "Y" ]]; then
    read -p "AWS Access Key ID: " aws_key
    read -sp "AWS Secret Access Key: " aws_secret
    echo ""
    read -p "AWS S3 Bucket Name (e.g., garcar-backups): " s3_bucket
    read -p "AWS Region (e.g., us-east-1): " aws_region
    
    echo "AWS_ACCESS_KEY_ID=$aws_key" >> "$SECRETS_FILE"
    echo "AWS_SECRET_ACCESS_KEY=$aws_secret" >> "$SECRETS_FILE"
    echo "S3_BUCKET=$s3_bucket" >> "$SECRETS_FILE"
    echo "AWS_REGION=$aws_region" >> "$SECRETS_FILE"
    echo -e "${GREEN}✅ AWS credentials added${NC}"
fi
echo ""

# Prompt for notification services (optional)
read -p "Configure Slack notifications? (y/n): " configure_slack
if [[ "$configure_slack" == "y" || "$configure_slack" == "Y" ]]; then
    read -p "Slack Webhook URL: " slack_webhook
    echo "SLACK_WEBHOOK_URL=$slack_webhook" >> "$SECRETS_FILE"
    echo -e "${GREEN}✅ Slack webhook added${NC}"
fi
echo ""

read -p "Configure PagerDuty alerts? (y/n): " configure_pagerduty
if [[ "$configure_pagerduty" == "y" || "$configure_pagerduty" == "Y" ]]; then
    read -p "PagerDuty Integration Key: " pd_key
    read -p "PagerDuty Webhook URL: " pd_webhook
    echo "PAGERDUTY_KEY=$pd_key" >> "$SECRETS_FILE"
    echo "PAGERDUTY_WEBHOOK=$pd_webhook" >> "$SECRETS_FILE"
    echo -e "${GREEN}✅ PagerDuty configuration added${NC}"
fi
echo ""

# Upload secrets to GitHub
echo "📤 Uploading secrets to GitHub..."
echo ""

read -p "Upload secrets to GitHub repository now? (y/n): " upload_secrets
if [[ "$upload_secrets" == "y" || "$upload_secrets" == "Y" ]]; then
    
    # Upload required secrets
    echo "Uploading JWT_SECRET..."
    echo -n "$JWT_SECRET" | gh secret set JWT_SECRET --repo="$REPO_OWNER/$REPO_NAME"
    
    echo "Uploading DB_PASSWORD..."
    echo -n "$DB_PASSWORD" | gh secret set DB_PASSWORD --repo="$REPO_OWNER/$REPO_NAME"
    
    echo "Uploading REDIS_PASSWORD..."
    echo -n "$REDIS_PASSWORD" | gh secret set REDIS_PASSWORD --repo="$REPO_OWNER/$REPO_NAME"
    
    echo "Uploading GRAFANA_PASSWORD..."
    echo -n "$GRAFANA_PASSWORD" | gh secret set GRAFANA_PASSWORD --repo="$REPO_OWNER/$REPO_NAME"
    
    # Upload kubeconfig if available
    if [ ! -z "$KUBECONFIG_BASE64" ]; then
        echo "Uploading KUBECONFIG..."
        echo -n "$KUBECONFIG_BASE64" | gh secret set KUBECONFIG --repo="$REPO_OWNER/$REPO_NAME"
    fi
    
    # Upload optional secrets if configured
    if [ ! -z "$aws_key" ]; then
        echo "Uploading AWS credentials..."
        echo -n "$aws_key" | gh secret set AWS_ACCESS_KEY_ID --repo="$REPO_OWNER/$REPO_NAME"
        echo -n "$aws_secret" | gh secret set AWS_SECRET_ACCESS_KEY --repo="$REPO_OWNER/$REPO_NAME"
        echo -n "$s3_bucket" | gh secret set S3_BUCKET --repo="$REPO_OWNER/$REPO_NAME"
        echo -n "$aws_region" | gh secret set AWS_REGION --repo="$REPO_OWNER/$REPO_NAME"
    fi
    
    if [ ! -z "$slack_webhook" ]; then
        echo "Uploading Slack webhook..."
        echo -n "$slack_webhook" | gh secret set SLACK_WEBHOOK_URL --repo="$REPO_OWNER/$REPO_NAME"
    fi
    
    if [ ! -z "$pd_key" ]; then
        echo "Uploading PagerDuty configuration..."
        echo -n "$pd_key" | gh secret set PAGERDUTY_KEY --repo="$REPO_OWNER/$REPO_NAME"
        echo -n "$pd_webhook" | gh secret set PAGERDUTY_WEBHOOK --repo="$REPO_OWNER/$REPO_NAME"
    fi
    
    echo ""
    echo -e "${GREEN}✅ All secrets uploaded to GitHub${NC}"
else
    echo -e "${YELLOW}⚠️  Secrets not uploaded. Upload manually from: $SECRETS_FILE${NC}"
    echo "Or run: gh secret set SECRET_NAME < value_file --repo=$REPO_OWNER/$REPO_NAME"
fi

echo ""
echo "🎉 Configuration Complete!"
echo "========================="
echo ""
echo "Next steps:"
echo "1. ✅ Secrets configured"
echo "2. 📝 Update domain names: ./scripts/update-domains.sh"
echo "3. 🌐 Configure DNS records: ./scripts/setup-dns.sh"
echo "4. 🚀 Deploy: git push origin main"
echo ""
echo "Secrets saved to: $SECRETS_FILE (keep secure!)"
echo ""
