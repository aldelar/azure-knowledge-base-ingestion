# Epic 010 — Agent Memory Layer

> **Status:** Draft
> **Created:** March 11, 2026
> **Updated:** March 11, 2026

## Objective

Move conversation memory management from the **web app middleware** to the **agent endpoint**, using the Microsoft Agent Framework's session persistence model (`AgentSession` + `AgentSessionRepository`).

After this epic:

- **Agent owns conversation history** — `InMemoryHistoryProvider` manages per-request context; a custom `CosmosAgentSessionRepository` persists `AgentSession` state (including message history) to Cosmos DB between requests.
- **Web app becomes a thin relay** — sends `conversation_id` via the Responses API protocol, reads from Cosmos DB for sidebar/resume only. No longer builds, trims, or passes full context.
- **Framework handles load/save lifecycle** — `from_agent_framework(agent, session_repository=...)` auto-loads the session before each request and saves it after.
- **Cosmos DB schema updated** — new `agent-sessions` container (partition key: `/conversationId`); legacy `conversations` container deleted.
- **Agent process remains stateless** — loads session from Cosmos at request start, saves at request end. Nothing is held in memory between requests.

## Success Criteria

- [ ] `agent-framework-core` upgraded to `1.0.0rc3`, `azure-ai-agentserver-agentframework` to `1.0.0b16`
- [ ] Agent creates `ChatAgent` with `InMemoryHistoryProvider` as context provider
- [ ] Custom `CosmosAgentSessionRepository` subclasses `SerializedAgentSessionRepository`
- [ ] `from_agent_framework()` receives `session_repository=CosmosAgentSessionRepository(...)`
- [ ] Agent container app has Cosmos DB RBAC role assignment and env vars (`COSMOS_ENDPOINT`, `COSMOS_DATABASE_NAME`)
- [ ] Cosmos DB `agent-sessions` container deployed with partition key `/conversationId`
- [ ] Web app passes `conversation_id` via `extra_body={"conversation": {"id": thread_id}}`
- [ ] Web app no longer builds `conversation_context`, no longer calls `_trim_context()`, no longer sends `instructions=conversation_context`
- [ ] Web app `on_chat_resume()` reads from `agent-sessions` container (not old `conversations`)
- [ ] Legacy `conversations` container removed from Bicep
- [ ] Multi-turn conversations persist across web app restarts (agent loads history from Cosmos)
- [ ] `make test` passes with zero regressions
- [ ] Architecture and agent-memory spec docs updated

---

## Background

### Current State

The web app owns all conversation memory via a client-side memory pattern:

| Aspect | Current Implementation |
|--------|------------------------|
| History ownership | Web app (`src/web-app/app/main.py`) |
| Context building | Web app serializes `messages[]` → `conversation_context` string |
| Context trimming | `_trim_context()` at 120K tokens via `tiktoken` |
| Persistence | Chainlit data layer → Cosmos DB `conversations` container |
| Agent receives | `instructions=conversation_context` (full history as system prompt) |
| Agent stores | Nothing — pure stateless request/response |
| Cosmos access | Web app only (system-assigned MI + `Built-in Data Contributor`) |
| SDK version | `agent-framework-core==1.0.0b260107`, `azure-ai-agentserver-agentframework==1.0.0b14` |

### Target State

The agent owns history via the framework's session/provider model:

| Aspect | Target Implementation |
|--------|----------------------|
| History ownership | Agent via `InMemoryHistoryProvider` + `CosmosAgentSessionRepository` |
| Context building | Framework auto-injects history from `AgentSession.state["messages"]` |
| Context trimming | None initially (deferred: compaction providers when SDK ships them) |
| Persistence | `SerializedAgentSessionRepository` → Cosmos DB `agent-sessions` container |
| Agent receives | User message only; history auto-loaded from Cosmos by framework |
| Agent stores | `AgentSession` (messages + state) auto-saved after each turn |
| Cosmos access | Both agent (read/write sessions) and web app (read for sidebar/resume) |
| SDK version | `agent-framework-core==1.0.0rc3`, `azure-ai-agentserver-agentframework==1.0.0b16` |

### Key Framework Components (rc3)

| Component | Module | Role |
|-----------|--------|------|
| `AgentSession` | `agent_framework._sessions` | Serializable session container with `.state` dict and `.to_dict()`/`.from_dict()` |
| `BaseHistoryProvider` | `agent_framework._sessions` | Abstract base: `get_messages()` / `save_messages()` hooks called before/after model invocation |
| `InMemoryHistoryProvider` | `agent_framework._sessions` | Default provider — stores messages in `session.state["messages"]` |
| `BaseContextProvider` | `agent_framework._sessions` | Base class for the `before_run` / `after_run` pipeline |
| `AgentSessionRepository` | `agentserver.agentframework.persistence` | ABC: `get(conversation_id)` → `AgentSession`, `set(conversation_id, session)` |
| `SerializedAgentSessionRepository` | `agentserver.agentframework.persistence` | Base with auto-serialize: implement `read_from_storage()` / `write_to_storage()` |
| `from_agent_framework()` | `agentserver.agentframework` | Adapter: `from_agent_framework(agent, session_repository=...)` handles load/save lifecycle |

### Compaction Status

The `_compaction` module (documented at [learn.microsoft.com](https://learn.microsoft.com/en-us/agent-framework/agents/conversations/compaction)) is **not yet available** in any published PyPI version — verified through `1.0.0rc3` (March 4, 2026). Compaction strategies (`TokenBudgetComposedStrategy`, `SummarizationStrategy`, `SlidingWindowStrategy`, etc.) are deferred to Story 10.

### API Migration Summary

The upgrade from beta to rc3 involves significant API changes:

| Concept | beta (`1.0.0b260107`) | rc3 (`1.0.0rc3`) |
|---------|------------------------|-------------------|
| Session type | `AgentThread` | `AgentSession` |
| History storage | `ContextProvider._memory` | `BaseHistoryProvider.get_messages()`/`save_messages()` |
| Provider pipeline | `context_providers: list[ContextProvider]` | `context_providers: list[BaseContextProvider]` |
| Adapter param | `thread_repository` | `session_repository` |
| Adapter repo ABC | `AgentThreadRepository` | `AgentSessionRepository` |
| Serialization | `AgentThread` (custom) | `AgentSession.to_dict()`/`.from_dict()` |

### Change Impact Summary

| Component | Action |
|-----------|--------|
| `src/agent/pyproject.toml` | **UPDATE** — bump `agent-framework-core` to `>=1.0.0rc3`, `azure-ai-agentserver-agentframework` to `>=1.0.0b16` |
| `src/agent/agent/config.py` | **UPDATE** — add `cosmos_endpoint`, `cosmos_database_name` |
| `src/agent/agent/kb_agent.py` | **UPDATE** — add `InMemoryHistoryProvider` to `context_providers` |
| `src/agent/agent/session_repository.py` | **NEW** — `CosmosAgentSessionRepository` (subclass `SerializedAgentSessionRepository`) |
| `src/agent/main.py` | **UPDATE** — instantiate `CosmosAgentSessionRepository`, pass to `from_agent_framework()` |
| `src/web-app/app/main.py` | **UPDATE** — pass `conversation_id`, remove context building + trim logic, simplify `on_chat_resume()` |
| `src/web-app/app/data_layer.py` | **UPDATE** — read from `agent-sessions` container for sidebar/resume |
| `infra/modules/cosmos-db.bicep` | **UPDATE** — add `agent-sessions` container, remove `conversations` container |
| `infra/modules/agent-container-app.bicep` | **UPDATE** — add `cosmosEndpoint`, `cosmosDatabaseName` env vars |
| `infra/main.bicep` | **UPDATE** — add Cosmos RBAC role for agent identity, pass Cosmos params to agent module |
| `docs/specs/agent-memory.md` | **UPDATE** — reflect new ownership model |
| `docs/specs/architecture.md` | **UPDATE** — memory flow in architecture diagram |

---

## Stories

### Story 1 — Upgrade SDK Packages ✍️

Upgrade `agent-framework-core` from `1.0.0b260107` to `1.0.0rc3` and `azure-ai-agentserver-agentframework` from `1.0.0b14` to `1.0.0b16`. Adapt existing agent code to the new API surface.

**Acceptance Criteria:**

- [ ] `src/agent/pyproject.toml` pins `agent-framework-core>=1.0.0rc3` and `azure-ai-agentserver-agentframework>=1.0.0b16`
- [ ] `agent-framework-azure-ai` updated to matching `1.0.0rc3`
- [ ] Existing agent code compiles and runs against new SDK (`ChatAgent`, `from_agent_framework`, tool definitions)
- [ ] Any import path changes in `kb_agent.py` or `main.py` resolved
- [ ] Agent starts locally (`make agent-dev`) and responds to a test query
- [ ] `make test` passes — all existing agent tests green

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/pyproject.toml` | Bump version pins |
| `src/agent/agent/kb_agent.py` | Fix imports if needed (verify `ChatAgent` API stable) |
| `src/agent/main.py` | Fix imports if needed (`from_agent_framework` signature change) |
| `src/agent/tests/` | Fix test imports if needed |

---

### Story 2 — Deploy `agent-sessions` Cosmos Container ✍️

Add the `agent-sessions` container to the Cosmos DB Bicep module. This container stores serialized `AgentSession` objects keyed by `conversationId`.

**Acceptance Criteria:**

- [ ] `infra/modules/cosmos-db.bicep` defines `agent-sessions` container with partition key `/conversationId`
- [ ] Indexing policy excludes `/state/*` (large message arrays) and `/"_etag"/?`
- [ ] TTL set to `-1` (no expiry — sessions persist indefinitely)
- [ ] `azd provision` succeeds with the new container
- [ ] Existing `conversations` container is NOT yet removed (removed in Story 9)

**Implementation Scope:**

| File | Change |
|------|--------|
| `infra/modules/cosmos-db.bicep` | Add `agent-sessions` container resource |

---

### Story 3 — Agent Cosmos DB RBAC & Environment Variables ✍️

Grant the agent container app's managed identity `Built-in Data Contributor` RBAC on Cosmos DB and inject the endpoint/database env vars.

**Acceptance Criteria:**

- [ ] `infra/main.bicep` adds a `cosmos-db-role` module instance for the agent container app identity (same pattern as existing `cosmosDbWebAppRole`)
- [ ] `infra/modules/agent-container-app.bicep` accepts `cosmosEndpoint` and `cosmosDatabaseName` parameters
- [ ] Agent container app has `COSMOS_ENDPOINT` and `COSMOS_DATABASE_NAME` environment variables
- [ ] `src/agent/agent/config.py` reads `COSMOS_ENDPOINT` and `COSMOS_DATABASE_NAME` from environment
- [ ] `azd provision` succeeds — agent identity can access Cosmos
- [ ] Infra docs updated if needed

**Implementation Scope:**

| File | Change |
|------|--------|
| `infra/main.bicep` | Add `cosmosDbAgentRole` module, pass Cosmos params to agent module |
| `infra/modules/agent-container-app.bicep` | Add `cosmosEndpoint`, `cosmosDatabaseName` params + env vars |
| `src/agent/agent/config.py` | Add `cosmos_endpoint`, `cosmos_database_name` fields |

---

### Story 4 — Cosmos Agent Session Repository ✍️

Implement `CosmosAgentSessionRepository` — a custom subclass of `SerializedAgentSessionRepository` that reads/writes serialized `AgentSession` dicts to the `agent-sessions` Cosmos container.

**Acceptance Criteria:**

- [ ] New file `src/agent/agent/session_repository.py` with `CosmosAgentSessionRepository`
- [ ] Subclasses `SerializedAgentSessionRepository` from `azure.ai.agentserver.agentframework.persistence`
- [ ] `read_from_storage(conversation_id)` reads from Cosmos using `conversation_id` as both document ID and partition key
- [ ] `write_to_storage(conversation_id, serialized_session)` upserts to Cosmos with `conversationId` as partition key
- [ ] Uses `DefaultAzureCredential` via `azure.cosmos.aio.CosmosClient` for async Cosmos access
- [ ] Constructor accepts `endpoint`, `database_name`, `container_name` parameters
- [ ] Unit tests mock Cosmos client and verify read/write/round-trip serialization
- [ ] Handles missing documents gracefully (returns `None` for unknown `conversation_id`)

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/agent/session_repository.py` | **NEW** — `CosmosAgentSessionRepository` |
| `src/agent/tests/test_session_repository.py` | **NEW** — unit tests |
| `src/agent/pyproject.toml` | Add `azure-cosmos` dependency if not already present |

---

### Story 5 — Wire Session Repository into Agent Entry Point ✍️

Connect `CosmosAgentSessionRepository` to the agent's HTTP server via `from_agent_framework()`, and add `InMemoryHistoryProvider` to the agent's context providers.

**Acceptance Criteria:**

- [ ] `src/agent/agent/kb_agent.py` passes `context_providers=[InMemoryHistoryProvider()]` to `ChatAgent()`
- [ ] `src/agent/main.py` instantiates `CosmosAgentSessionRepository` with config values
- [ ] `from_agent_framework(agent, session_repository=cosmos_repo)` wired in `main.py`
- [ ] Multi-turn test: send two messages with the same `conversation_id` → agent receives history from first message when processing second
- [ ] Agent still works for new conversations (no prior session in Cosmos)
- [ ] `make test` passes

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/agent/kb_agent.py` | Add `context_providers=[InMemoryHistoryProvider()]` |
| `src/agent/main.py` | Instantiate repo, pass `session_repository=` to `from_agent_framework()` |
| `src/agent/tests/test_multi_turn.py` | **NEW** — integration test for multi-turn persistence |

---

### Story 6 — Web App: Pass conversation_id, Stop Building Context ✍️

Update the web app to pass `conversation_id` to the agent endpoint via the Responses API protocol and remove all context-building logic. The agent now owns history — the web app just relays user messages.

**Acceptance Criteria:**

- [ ] `_call_agent()` passes `extra_body={"conversation": {"id": thread_id}}` in the Responses API call
- [ ] `conversation_context` string building removed from `on_message()`
- [ ] `instructions=conversation_context` no longer sent — agent gets its own instructions via `InMemoryHistoryProvider`
- [ ] `messages` list no longer maintained in web app session
- [ ] `_format_messages_for_context()` (or equivalent) removed
- [ ] Streaming response still works end-to-end
- [ ] `make test` passes

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/web-app/app/main.py` | Remove context building, add `conversation_id` to request |

---

### Story 7 — Web App: Remove Trim Logic & Simplify Resume ✍️

Remove `_trim_context()` (the 120K token trimming) and simplify `on_chat_resume()` to read from the new `agent-sessions` container instead of rebuilding context from Chainlit steps.

**Acceptance Criteria:**

- [ ] `_trim_context()` function removed from `main.py`
- [ ] `tiktoken` dependency removed from `src/web-app/pyproject.toml` (if no other use)
- [ ] `on_chat_resume()` reads message history from `agent-sessions` Cosmos container for display
- [ ] Sidebar conversation list still works (list conversations, click to resume)
- [ ] Resumed conversations continue correctly (agent receives `conversation_id`, loads history from Cosmos)
- [ ] `make test` passes

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/web-app/app/main.py` | Remove `_trim_context()`, rewrite `on_chat_resume()` |
| `src/web-app/pyproject.toml` | Remove `tiktoken` if unused |

---

### Story 8 — Web App: Switch Data Layer to `agent-sessions` Container ✍️

Update the web app's Cosmos data layer to read from the `agent-sessions` container (written by the agent) instead of the legacy `conversations` container. The web app needs read access for sidebar listing and conversation resume.

**Acceptance Criteria:**

- [ ] `src/web-app/app/data_layer.py` reads from `agent-sessions` container
- [ ] Container name configurable via env var (`COSMOS_SESSIONS_CONTAINER` or similar)
- [ ] Conversation list query works with new `/conversationId` partition key
- [ ] Message display on resume correctly deserializes `AgentSession.state["messages"]`
- [ ] Web app Cosmos env vars updated in Bicep if container name changed
- [ ] `make test` passes

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/web-app/app/data_layer.py` | Point to `agent-sessions` container, adapt queries |
| `src/web-app/app/config.py` | Add `cosmos_sessions_container` if needed |
| `infra/modules/container-app.bicep` | Update container name env var if needed |

---

### Story 9 — Delete Legacy `conversations` Container ✍️

Remove the `conversations` container from Cosmos DB Bicep now that all reads/writes use `agent-sessions`.

**Acceptance Criteria:**

- [ ] `conversations` container resource removed from `infra/modules/cosmos-db.bicep`
- [ ] No code references `conversations` container (grep confirms)
- [ ] `azd provision` succeeds
- [ ] `docs/specs/agent-memory.md` updated — documents `agent-sessions` as the sole container
- [ ] `docs/specs/infrastructure.md` updated if Cosmos section references container names
- [ ] `make test` passes

**Implementation Scope:**

| File | Change |
|------|--------|
| `infra/modules/cosmos-db.bicep` | Remove `conversationsContainer` resource |
| `docs/specs/agent-memory.md` | Full rewrite — new ownership model, new schema |
| `docs/specs/infrastructure.md` | Update Cosmos section |

---

### Story 10 — Conversation Compaction (Deferred) ✍️

> **Blocked:** The `_compaction` module (`CompactionProvider`, `TokenBudgetComposedStrategy`, `SummarizationStrategy`, `SlidingWindowStrategy`) is documented but **not yet published** in any PyPI release of `agent-framework-core` (verified through `1.0.0rc3`). This story is ready to implement once the module ships.

Add compaction strategies to prevent unbounded conversation growth. When available, compose a `TokenBudgetComposedStrategy` pipeline:

1. **`ToolResultCompactionStrategy`** — trim verbose tool call results
2. **`SummarizationStrategy`** — summarize older messages (using `gpt-4o-mini`)
3. **`SlidingWindowStrategy`** — keep only the most recent N messages as fallback

**Acceptance Criteria:**

- [ ] `agent-framework-core` version with `_compaction` module identified and pinned (use `--prerelease=allow` — compaction will likely ship in a pre-release)
- [ ] `CompactionProvider` added to agent's `context_providers` pipeline
- [ ] `TokenBudgetComposedStrategy` configured with tool-result → summarization → sliding-window chain
- [ ] Summarization uses `gpt-4o-mini` deployment (add `summarizer_model_deployment_name` to agent config)
- [ ] Token budget set to a reasonable limit (e.g., 80% of model context window)
- [ ] Long conversation test: 50+ turns → verify compaction triggers, context stays within budget
- [ ] `make test` passes

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/pyproject.toml` | Bump to version with `_compaction` |
| `src/agent/agent/kb_agent.py` | Add `CompactionProvider` to `context_providers` |
| `src/agent/agent/config.py` | Add `summarizer_model_deployment_name` |
| `src/agent/tests/test_compaction.py` | **NEW** — compaction integration tests |

---

## Definition of Done

- [ ] All stories 1–9 completed and marked ✅
- [ ] Agent owns conversation history — loads/saves `AgentSession` from Cosmos per request
- [ ] Web app is a thin relay — passes `conversation_id`, reads Cosmos for display only
- [ ] Multi-turn conversations work across restarts
- [ ] No data in legacy `conversations` container (container deleted)
- [ ] `make test` passes with zero regressions
- [ ] `docs/specs/agent-memory.md` and `docs/specs/architecture.md` updated
- [ ] Story 10 documented as deferred with clear readiness criteria
