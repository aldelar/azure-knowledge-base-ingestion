# ARD-005: Foundry Hosted Agent Deployment

> **Status:** Accepted
> **Date:** 2026-02-25
> **Decision Makers:** Engineering Team

## Context

The KB Agent is a FastAPI-based service that provides vision-grounded, search-augmented answers via the OpenAI Responses API. It uses Microsoft Agent Framework (`ChatAgent`) with a `search_knowledge_base` tool, vision middleware for image injection, and custom SSE streaming with citation metadata.

The agent needs to be deployed to Azure alongside the web app. The question is **how** to deploy the agent — as a standalone Container App, or as a Foundry hosted agent within the Azure AI Foundry project.

## Decision

**Deploy the KB Agent as a Foundry hosted agent** using AZD's `azure.ai.agents` extension, while keeping our custom FastAPI server implementation.

### What This Means

- The agent container is built in ACR via remote build and deployed to the Foundry project
- Foundry provides a stable HTTPS endpoint with Entra ID authentication, managed identity, and a hosting runtime
- The web app calls the agent via the Foundry endpoint using `DefaultAzureCredential` (Entra token auth)
- The agent identity is managed by Foundry (separate from the Container App identity), with explicit RBAC role assignments for AI Services, AI Search, and Blob Storage

### Configuration

The AZD agent service uses:
- `host: azure.ai.agent` — Foundry hosted agent deployment target
- `language: docker` with `remoteBuild: true` — container built in ACR
- `config.container` — CPU/memory/scale settings for the hosted container
- `config.deployments` — model deployment declarations (gpt-4.1)

The agent manifest (`agent.yaml`) uses the `ContainerAgent` schema:
- `kind: hosted` — indicates a hosted container agent
- `protocols: [{protocol: responses, version: v1}]` — the agent implements the Responses API
- `environment_variables` — config values injected into the container at runtime

## Alternatives Considered

### Alternative 1: Deploy Agent as Standalone Container App (Rejected)

Deploy the agent as a second Container App alongside the web app, using the existing Container Apps Environment.

- **Pros:** Simpler — no Foundry-specific configuration, reuses existing Container App patterns. Full control over networking and scaling.
- **Cons:** No Foundry integration — no managed agent identity, no Foundry tracing, no agent lifecycle management. The web app would need a different auth pattern (service-to-service within Container Apps Environment). Does not leverage the Foundry project we already provision. Misaligned with the platform direction for agent hosting.

### Alternative 2: Use Foundry Hosting Adapter (Rejected)

Adopt the official `azure-ai-agentserver-agentframework` package and wrap our agent with `from_agent_framework(agent).run()`.

- **Pros:** Officially recommended pattern. Automatically exposes the correct REST surface. Simpler entrypoint code.
- **Cons:** We lose our custom SSE streaming with citation metadata injection — the adapter controls the response format and doesn't support custom `metadata` fields in `response.completed` events. Our web app depends on this metadata for rendering clickable `[Ref #N]` citations with side-panel detail views. Switching would require reworking the citation flow in both the agent and web app. The adapter also doesn't support our `/v1/entities` endpoint (agent discovery). The adapter package (`azure-ai-agentserver-agentframework`) may conflict with our existing `agent-framework-core` and `agent-framework-azure-ai` packages.

### Alternative 3: Deploy via `az cognitiveservices account agent publish` Only (Deferred)

Use the publish CLI command without AZD integration.

- **Pros:** Direct control over the publish step. Already partially scripted in `scripts/publish-agent.sh`.
- **Cons:** Bypasses AZD's service lifecycle (build → push → deploy). The publish command expects the agent container to already be deployed. Unclear how it interacts with the AZD extension's deployment flow. May be needed as a post-deploy step for RBAC assignment regardless.

## Consequences

1. **`azure.yaml`** agent service updated to `host: azure.ai.agent` with proper `config` block
2. **`agent.yaml`** rewritten in `ContainerAgent` schema format
3. **AZD environment** needs additional variables (`AZURE_AI_PROJECT_ID`, `AZURE_AI_PROJECT_ENDPOINT`, etc.)
4. **Agent code unchanged** — FastAPI server, streaming, citations, vision middleware all preserved
5. **Web App unchanged** — `_create_agent_client()` already handles `https://` endpoints with Entra token auth
6. **RBAC** — published agent identity needs roles on AI Services, AI Search, and Serving Storage (existing `publish-agent.sh` script handles this)
7. **Observability** — Foundry provides built-in tracing; `APPLICATIONINSIGHTS_CONNECTION_STRING` is injected automatically

## References

- [Research 006: Foundry Hosted Agent Deployment](../research/006-foundry-hosted-agent-deployment.md)
- [AZD AI Agent Extension](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/extensions/azure-ai-foundry-extension)
- [Hosted Agents Concept](https://learn.microsoft.com/en-us/azure/ai-services/agents/concepts/hosted-agents)
