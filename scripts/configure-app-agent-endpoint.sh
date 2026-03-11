#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# configure-app-agent-endpoint.sh — Set web app's AGENT_ENDPOINT to the
# registered agent proxy URL (from APIM gateway registration).
# ---------------------------------------------------------------------------
# Idempotent — safe to re-run. Updates the web app Container App's
# AGENT_ENDPOINT env var to point to the registered agent URL.
#
# Prerequisites:
#   - azd env has AGENT_REGISTERED_URL (set by register-agent.sh)
#   - Web app Container App is deployed
# ---------------------------------------------------------------------------
set -euo pipefail

echo "=== Configure Web App Agent Endpoint ==="
echo ""

# Read values from AZD env
AGENT_REGISTERED_URL=$(azd env get-value AGENT_REGISTERED_URL 2>/dev/null || echo "")
WEBAPP_NAME=$(azd env get-value WEBAPP_NAME)
RESOURCE_GROUP=$(azd env get-value RESOURCE_GROUP)

if [ -z "$AGENT_REGISTERED_URL" ]; then
  echo "WARNING: AGENT_REGISTERED_URL not set in AZD env."
  echo "  Run 'make azure-register-agent' first."
  echo "  Skipping web app configuration."
  exit 0
fi

echo "  Web App:            $WEBAPP_NAME"
echo "  Resource Group:     $RESOURCE_GROUP"
echo "  Agent Endpoint:     $AGENT_REGISTERED_URL"
echo ""

echo "Updating web app AGENT_ENDPOINT..."
az containerapp update \
  --name "$WEBAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "AGENT_ENDPOINT=$AGENT_REGISTERED_URL" \
  -o none

echo "  Web app AGENT_ENDPOINT updated to: $AGENT_REGISTERED_URL"
echo ""
echo "=== Done ==="
