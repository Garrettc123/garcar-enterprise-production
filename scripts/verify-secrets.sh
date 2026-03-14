#!/usr/bin/env bash
# =============================================================================
# Garcar Enterprise — Verify All GitHub Secrets Are Set
# Usage: bash scripts/verify-secrets.sh
# =============================================================================
set -euo pipefail

REPO="Garrettc123/garcar-enterprise-production"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "  ====================================================="
echo "    Garcar Enterprise — Secrets Verification"
echo "  ====================================================="
echo -e "${NC}"

if ! command -v gh &>/dev/null; then
  echo -e "${RED}❌ gh CLI not found. Install: https://cli.github.com/${NC}"
  exit 1
fi

# Get list of set secrets
SET_SECRETS=$(gh secret list --repo "$REPO" --json name -q '.[].name' 2>/dev/null || echo "")

REQUIRED=(
  DB_HOST DB_PASSWORD
  AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
  STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
  GARCAR_API_KEY JWT_SECRET
)

OPTIONAL=(
  REDIS_PASSWORD GRAFANA_PASSWORD
  SLACK_WEBHOOK_URL PAGERDUTY_WEBHOOK PAGERDUTY_KEY
)

MISSING=0

echo -e "${BLUE}Required Secrets:${NC}"
for SECRET in "${REQUIRED[@]}"; do
  if echo "$SET_SECRETS" | grep -q "^${SECRET}$"; then
    echo -e "  ${GREEN}✅ $SECRET${NC}"
  else
    echo -e "  ${RED}❌ $SECRET — MISSING${NC}"
    ((MISSING++)) || true
  fi
done

echo ""
echo -e "${BLUE}Optional Secrets:${NC}"
for SECRET in "${OPTIONAL[@]}"; do
  if echo "$SET_SECRETS" | grep -q "^${SECRET}$"; then
    echo -e "  ${GREEN}✅ $SECRET${NC}"
  else
    echo -e "  ${YELLOW}⚠️  $SECRET — not set (optional)${NC}"
  fi
done

echo ""
if [ $MISSING -eq 0 ]; then
  echo -e "${GREEN}✅ All required secrets are set. Ready to deploy!${NC}"
else
  echo -e "${RED}❌ $MISSING required secret(s) missing.${NC}"
  echo -e "  Run: ${YELLOW}bash scripts/setup-secrets.sh${NC} to add them."
  exit 1
fi
