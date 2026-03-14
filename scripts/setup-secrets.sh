#!/usr/bin/env bash
# =============================================================================
# Garcar Enterprise — Automated GitHub Secrets Setup
# Usage: bash scripts/setup-secrets.sh
# Requirements: gh CLI authenticated (gh auth login)
# =============================================================================
set -euo pipefail

REPO="Garrettc123/garcar-enterprise-production"
ENV_FILE=".env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "  ====================================================="
echo "    Garcar Enterprise — GitHub Secrets Automation"
echo "  ====================================================="
echo -e "${NC}"

# ---- Prereq check -----------------------------------------------------------
if ! command -v gh &>/dev/null; then
  echo -e "${RED}❌ GitHub CLI (gh) not found.${NC}"
  echo "  Install: https://cli.github.com/"
  echo "  Then run: gh auth login"
  exit 1
fi

if ! gh auth status &>/dev/null; then
  echo -e "${RED}❌ Not authenticated. Run: gh auth login${NC}"
  exit 1
fi

echo -e "${GREEN}✅ GitHub CLI authenticated${NC}"

# ---- Load .env if it exists -------------------------------------------------
if [ -f "$ENV_FILE" ]; then
  echo -e "${GREEN}✅ Found $ENV_FILE — loading values${NC}"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo -e "${YELLOW}⚠️  No .env file found. You'll be prompted for each secret.${NC}"
  echo "  Tip: Copy .env.example to .env and fill in your values first."
  echo ""
fi

# ---- Secret definitions (name:env_var:description) -------------------------
declare -A SECRETS
SECRETS=(
  [DB_HOST]="DB_HOST:PostgreSQL host (RDS endpoint or IP)"
  [DB_PASSWORD]="DB_PASSWORD:PostgreSQL password"
  [REDIS_PASSWORD]="REDIS_PASSWORD:Redis password"
  [JWT_SECRET]="JWT_SECRET:JWT signing secret (min 32 chars)"
  [AWS_ACCESS_KEY_ID]="AWS_ACCESS_KEY_ID:AWS IAM access key ID"
  [AWS_SECRET_ACCESS_KEY]="AWS_SECRET_ACCESS_KEY:AWS IAM secret access key"
  [STRIPE_SECRET_KEY]="STRIPE_SECRET_KEY:Stripe secret key (sk_live_... or sk_test_...)"
  [STRIPE_WEBHOOK_SECRET]="STRIPE_WEBHOOK_SECRET:Stripe webhook signing secret (whsec_...)"
  [GARCAR_API_KEY]="GARCAR_API_KEY:Internal Garcar API key for agent orchestration"
  [GRAFANA_PASSWORD]="GRAFANA_PASSWORD:Grafana admin password"
  [SLACK_WEBHOOK_URL]="SLACK_WEBHOOK_URL:Slack webhook URL (optional)"
  [PAGERDUTY_WEBHOOK]="PAGERDUTY_WEBHOOK:PagerDuty events URL (optional)"
  [PAGERDUTY_KEY]="PAGERDUTY_KEY:PagerDuty integration key (optional)"
)

# Ordered list for clean output
ORDERED_KEYS=(
  DB_HOST DB_PASSWORD REDIS_PASSWORD JWT_SECRET
  AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
  STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
  GARCAR_API_KEY GRAFANA_PASSWORD
  SLACK_WEBHOOK_URL PAGERDUTY_WEBHOOK PAGERDUTY_KEY
)

SET_COUNT=0
SKIP_COUNT=0
FAIL_COUNT=0

echo -e "${BLUE}➡️  Setting secrets for: $REPO${NC}"
echo ""

for KEY in "${ORDERED_KEYS[@]}"; do
  IFS=':' read -r ENV_VAR DESCRIPTION <<< "${SECRETS[$KEY]}"

  # Get value from env or prompt
  VALUE="${!ENV_VAR:-}"

  if [ -z "$VALUE" ]; then
    echo -e "${YELLOW}✏️  $KEY${NC} — $DESCRIPTION"
    read -rsp "   Enter value (leave blank to skip): " VALUE
    echo ""
  fi

  if [ -z "$VALUE" ]; then
    echo -e "   ${YELLOW}⏭️  Skipped $KEY${NC}"
    ((SKIP_COUNT++)) || true
    continue
  fi

  if echo -n "$VALUE" | gh secret set "$KEY" --repo "$REPO" 2>/dev/null; then
    echo -e "   ${GREEN}✅ Set $KEY${NC}"
    ((SET_COUNT++)) || true
  else
    echo -e "   ${RED}❌ Failed to set $KEY${NC}"
    ((FAIL_COUNT++)) || true
  fi
done

echo ""
echo -e "${BLUE}=====================================================${NC}"
echo -e "  ${GREEN}✅ Set:     $SET_COUNT secrets${NC}"
echo -e "  ${YELLOW}⏭️  Skipped: $SKIP_COUNT secrets${NC}"
[ $FAIL_COUNT -gt 0 ] && echo -e "  ${RED}❌ Failed:  $FAIL_COUNT secrets${NC}"
echo -e "${BLUE}=====================================================${NC}"
echo ""
echo -e "${GREEN}Done! View secrets at:${NC}"
echo "  https://github.com/$REPO/settings/secrets/actions"
