#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# publish-agent.sh — Publish the KB Agent to Foundry and assign RBAC
# ---------------------------------------------------------------------------
# Workflow:
#   1. Publish the agent (creates a dedicated identity + stable endpoint)
#   2. Retrieve the published agent's identity (principal ID)
#   3. Assign RBAC roles to the published agent identity:
#      - Cognitive Services OpenAI User  (AI Services — reasoning + embeddings)
#      - Search Index Data Reader        (AI Search — query index)
#      - Storage Blob Data Reader        (Serving Storage — download images)
#   4. Store the agent endpoint URL in AZD env for web app deployment
#
# Prerequisites:
#   - azd env is configured (run `azd provision` first)
#   - Agent is deployed in dev mode (`azd deploy --service agent`)
#   - az CLI logged in with sufficient permissions
# ---------------------------------------------------------------------------
set -euo pipefail

echo "=== Publish KB Agent to Foundry ==="
echo ""

# ---------------------------------------------------------------------------
# 1. Read environment values from AZD
# ---------------------------------------------------------------------------
AI_SERVICES_NAME=$(azd env get-value AI_SERVICES_NAME)
RESOURCE_GROUP=$(azd env get-value RESOURCE_GROUP)
FOUNDRY_PROJECT_NAME=$(azd env get-value FOUNDRY_PROJECT_NAME)
SEARCH_SERVICE_NAME=$(azd env get-value SEARCH_SERVICE_NAME)
SERVING_STORAGE_ACCOUNT=$(azd env get-value SERVING_STORAGE_ACCOUNT)

echo "  AI Services:     $AI_SERVICES_NAME"
echo "  Project:         $FOUNDRY_PROJECT_NAME"
echo "  Resource Group:  $RESOURCE_GROUP"
echo "  Search:          $SEARCH_SERVICE_NAME"
echo "  Serving Storage: $SERVING_STORAGE_ACCOUNT"
echo ""

# ---------------------------------------------------------------------------
# 2. Publish the agent
# ---------------------------------------------------------------------------
echo "Publishing agent..."
PUBLISH_OUTPUT=$(az cognitiveservices account agent publish \
    --name "$AI_SERVICES_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --agent-name "kb-agent" \
    --output json 2>&1) || {
    echo "ERROR: Failed to publish agent."
    echo "$PUBLISH_OUTPUT"
    exit 1
}

echo "  Agent published successfully."
echo ""

# ---------------------------------------------------------------------------
# 3. Get the published agent endpoint and identity
# ---------------------------------------------------------------------------
AGENT_ENDPOINT=$(echo "$PUBLISH_OUTPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
# The endpoint URL varies by response format; try common keys
for key in ('endpoint', 'properties.endpoint', 'url'):
    parts = key.split('.')
    val = data
    for p in parts:
        val = val.get(p, {}) if isinstance(val, dict) else {}
    if val and isinstance(val, str):
        print(val)
        sys.exit(0)
# Fallback: construct from project endpoint
print('')
" 2>/dev/null || echo "")

AGENT_PRINCIPAL_ID=$(echo "$PUBLISH_OUTPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
# Try common locations for the agent identity principal ID
for path in [
    ['identity', 'principalId'],
    ['properties', 'identity', 'principalId'],
    ['agentIdentity', 'principalId'],
]:
    val = data
    for p in path:
        val = val.get(p, {}) if isinstance(val, dict) else {}
    if val and isinstance(val, str):
        print(val)
        sys.exit(0)
print('')
" 2>/dev/null || echo "")

if [ -z "$AGENT_ENDPOINT" ]; then
    echo "WARNING: Could not extract agent endpoint from publish output."
    echo "         You may need to retrieve it manually from the Foundry portal."
    echo "         Raw output:"
    echo "$PUBLISH_OUTPUT" | python3 -m json.tool 2>/dev/null || echo "$PUBLISH_OUTPUT"
    echo ""
fi

if [ -n "$AGENT_ENDPOINT" ]; then
    echo "  Agent endpoint: $AGENT_ENDPOINT"
fi

# ---------------------------------------------------------------------------
# 4. Assign RBAC to the published agent identity
# ---------------------------------------------------------------------------
if [ -n "$AGENT_PRINCIPAL_ID" ]; then
    echo ""
    echo "Assigning RBAC roles to agent identity ($AGENT_PRINCIPAL_ID)..."

    # Cognitive Services OpenAI User (AI Services — reasoning + embeddings)
    echo "  → Cognitive Services OpenAI User on AI Services..."
    AI_SERVICES_ID=$(az cognitiveservices account show \
        --name "$AI_SERVICES_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv)
    az role assignment create \
        --assignee-object-id "$AGENT_PRINCIPAL_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "Cognitive Services OpenAI User" \
        --scope "$AI_SERVICES_ID" \
        --only-show-errors 2>/dev/null || echo "    (may already exist)"

    # Search Index Data Reader (AI Search — query index)
    echo "  → Search Index Data Reader on AI Search..."
    SEARCH_ID=$(az search service show \
        --name "$SEARCH_SERVICE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv)
    az role assignment create \
        --assignee-object-id "$AGENT_PRINCIPAL_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "Search Index Data Reader" \
        --scope "$SEARCH_ID" \
        --only-show-errors 2>/dev/null || echo "    (may already exist)"

    # Storage Blob Data Reader (Serving Storage — download images for vision)
    echo "  → Storage Blob Data Reader on Serving Storage..."
    STORAGE_ID=$(az storage account show \
        --name "$SERVING_STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv)
    az role assignment create \
        --assignee-object-id "$AGENT_PRINCIPAL_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "Storage Blob Data Reader" \
        --scope "$STORAGE_ID" \
        --only-show-errors 2>/dev/null || echo "    (may already exist)"

    echo "  RBAC assignments complete."
else
    echo ""
    echo "WARNING: Could not extract agent principal ID from publish output."
    echo "         RBAC roles must be assigned manually."
    echo "         Raw output:"
    echo "$PUBLISH_OUTPUT" | python3 -m json.tool 2>/dev/null || echo "$PUBLISH_OUTPUT"
fi

# ---------------------------------------------------------------------------
# 5. Store agent endpoint in AZD env
# ---------------------------------------------------------------------------
if [ -n "$AGENT_ENDPOINT" ]; then
    echo ""
    echo "Storing AGENT_ENDPOINT in AZD environment..."
    azd env set AGENT_ENDPOINT "$AGENT_ENDPOINT"
    echo "  AGENT_ENDPOINT=$AGENT_ENDPOINT"
    echo ""
    echo "To update the web app with the new agent endpoint:"
    echo "  make azure-deploy-app"
fi

echo ""
echo "=== Done ==="
