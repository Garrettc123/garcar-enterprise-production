#!/bin/bash
set -euo pipefail

echo "⏪ Rolling back Garcar Enterprise deployment..."

SERVICE=${1:-all}

if [ "$SERVICE" == "all" ] || [ "$SERVICE" == "revenue-aggregator" ]; then
    echo "Rolling back revenue-aggregator..."
    kubectl rollout undo deployment/revenue-aggregator -n garcar-prod
fi

if [ "$SERVICE" == "all" ] || [ "$SERVICE" == "ai-agent-hub" ]; then
    echo "Rolling back ai-agent-hub..."
    kubectl rollout undo deployment/ai-agent-hub -n garcar-prod
fi

if [ "$SERVICE" == "all" ] || [ "$SERVICE" == "api-gateway" ]; then
    echo "Rolling back api-gateway..."
    kubectl rollout undo deployment/api-gateway -n garcar-prod
fi

echo "✅ Rollback complete"
kubectl get pods -n garcar-prod
