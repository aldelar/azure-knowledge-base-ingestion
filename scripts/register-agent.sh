#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# register-agent.sh — Register KB Agent in Foundry (Operate → Assets)
# ---------------------------------------------------------------------------
# Registers the agent in the Foundry portal without deploying it.
# The agent runs as a Container App; this script just creates/updates
# the agent entry so it appears under Operate → Assets with traces.
#
# Idempotent — re-running updates the existing registration.
#
# Prerequisites:
#   - azd env is configured (run `azd provision` first)
#   - Agent Container App is deployed (`azd deploy --service agent`)
#   - az CLI logged in
# ---------------------------------------------------------------------------
set -euo pipefail

echo "=== Register KB Agent in Foundry ==="
echo ""

# ---------------------------------------------------------------------------
# 1. Read environment values from AZD
# ---------------------------------------------------------------------------
AI_SERVICES_NAME=$(azd env get-value AI_SERVICES_NAME)
RESOURCE_GROUP=$(azd env get-value RESOURCE_GROUP)
FOUNDRY_PROJECT_NAME=$(azd env get-value FOUNDRY_PROJECT_NAME 2>/dev/null || azd env get-value AZURE_AI_PROJECT_NAME)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "  AI Services:    $AI_SERVICES_NAME"
echo "  Project:        $FOUNDRY_PROJECT_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Subscription:   $SUBSCRIPTION_ID"
echo ""

# ARM API base path
ARM_BASE="https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$AI_SERVICES_NAME/projects/$FOUNDRY_PROJECT_NAME"
API_VERSION="2025-10-01-preview"

# ---------------------------------------------------------------------------
# 2. Register agent application (no deployment — registration only)
# ---------------------------------------------------------------------------
echo "Registering agent application..."
REGISTER_OUTPUT=$(az rest --method PUT \
    --url "$ARM_BASE/applications/kb-agent?api-version=$API_VERSION" \
    --body '{"properties":{"displayName":"KB Agent","agents":[{"agentName":"kb-agent"}]}}' \
    -o json 2>&1) || {
    echo "ERROR: Failed to register agent."
    echo "$REGISTER_OUTPUT"
    exit 1
}

echo "  Agent registered as 'kb-agent' in Foundry."
echo ""

# Extract display info
APP_STATE=$(echo "$REGISTER_OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('properties',{}).get('provisioningState','Unknown'))" 2>/dev/null || echo "Unknown")
echo "  Provisioning state: $APP_STATE"
echo ""
echo "View in Foundry portal: https://ai.azure.com"
echo "  → Project: $FOUNDRY_PROJECT_NAME → Operate → Assets"
echo ""
echo "=== Done ==="
