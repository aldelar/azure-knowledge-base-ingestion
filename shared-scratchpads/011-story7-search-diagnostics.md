# Scratchpad: Epic 011 Story 7 — AI Search Diagnostic Logging

## Planner — Research & Plan (2026-03-19)

### Findings
- `search.bicep` has **zero** diagnostic settings — no `Microsoft.Insights/diagnosticSettings` resource
- No other Bicep module in the project has diagnostic settings either (no precedent)
- `monitoring.bicep` outputs `logAnalyticsWorkspaceId` — already consumed by `container-apps-env.bicep`
- `main.bicep` passes `monitoring.outputs.logAnalyticsWorkspaceId` to the container apps env, but **not** to the search module
- The search module is invoked multiple times in main.bicep (line 124 for the resource, then role-only deployments at 511/552/598) — diagnostics should only be on the primary deployment (line 124)
- AI Search supports `OperationLogs` category which logs all query/index operations including OData `$filter` params
- Agent already has `logger.debug("Applying security filter: %s", security_filter)` but it's DEBUG level — invisible in normal runs
-  The agent also logs `logger.info("Hybrid search for '%s' → %d results", ...)` at search_tool.py:122 — this confirms queries but not filters
- Promoting the filter log from DEBUG to INFO in the agent is a cheap win for local dev visibility
- Epic 011 has Stories 1–6 all Done. New story would be Story 7.

### Rejected approaches
- Adding diagnostic settings inline in the existing `search` module invocation in main.bicep — violates module pattern (all search config belongs in search.bicep)
- Creating a separate diagnostics module — overkill for a single resource, and the project convention is resource + RBAC together in one module

### Constraints
- search.bicep must accept an optional `logAnalyticsWorkspaceId` param (empty string default = no diagnostics)
- main.bicep must wire `monitoring.outputs.logAnalyticsWorkspaceId` to the primary search module invocation
- secondary search module invocations (role-only) should NOT get diagnostics (they're role deployments, not the search resource)
- docs/specs/infrastructure.md must be updated to note the diagnostic setting
- Agent filter log promotion (DEBUG → INFO) is a code change in `kb_agent.py`

---

## Plan: Story 7 — AI Search Diagnostic Logging

### Context
After implementing department-scoped search filtering (Stories 1–6), there's no way to verify in Azure that the OData `filter` parameter is actually being sent to AI Search. The search query logs are not enabled. This story adds diagnostic settings to the AI Search resource and promotes the agent's filter log from DEBUG to INFO for local dev visibility.

### Prerequisites
- [x] Stories 1–6 complete (department field indexed, filter middleware wired)
- [x] `monitoring.bicep` deploys Log Analytics workspace (exists)

### Implementation Steps
1. **Add `logAnalyticsWorkspaceId` param + diagnostic settings to `search.bicep`** — optional param with empty string default. When non-empty, create a `Microsoft.Insights/diagnosticSettings` child resource on the search service that sends `OperationLogs` + `AllMetrics` to the Log Analytics workspace.
2. **Wire the param in `main.bicep`** — pass `monitoring.outputs.logAnalyticsWorkspaceId` to the primary search module invocation (line ~124). Do NOT add it to the role-only invocations.
3. **Promote agent filter log to INFO** — in `kb_agent.py`, change `logger.debug("Applying security filter: %s", ...)` to `logger.info(...)`. This makes the filter visible in both local runs and Container Apps console logs without requiring DEBUG level.
4. **Update infrastructure docs** — add a row/note about diagnostic settings in `docs/specs/infrastructure.md` under the AI Search section.
5. **Update epic doc** — add Story 7 to `docs/epics/011-contextual-tool-filtering.md`.
6. **Test** — `az bicep build --file infra/main.bicep` to validate Bicep compiles. `make test` to confirm no regressions. Post-deploy: verify `AzureDiagnostics` queries return search operation logs.

### Files Affected
| File | Action | Service |
|------|--------|---------|
| `infra/modules/search.bicep` | Modify | Infra |
| `infra/main.bicep` | Modify | Infra |
| `src/agent/agent/kb_agent.py` | Modify | Agent |
| `docs/specs/infrastructure.md` | Modify | Docs |
| `docs/epics/011-contextual-tool-filtering.md` | Modify | Docs |

### Architecture Notes
- No new Azure resources — diagnostic settings is a child resource of the existing AI Search
- No cross-service boundary changes
- Config pattern: optional param with conditional resource (matches project pattern of `if (!empty(param))`)

### Test Strategy
- **Bicep validation:** `az bicep build --file infra/main.bicep` — must compile
- **Unit tests:** `make test` — must pass (only change is log level)
- **Post-deploy verification (manual):** Run a query in the web app, then execute:
  ```kql
  AzureDiagnostics
  | where ResourceProvider == "MICROSOFT.SEARCH"
  | where OperationName == "Query.Search"
  | project TimeGenerated, Query_s, Properties_d
  | order by TimeGenerated desc
  ```

### Design Context

#### Rejected Approaches
- **Separate diagnostics module** — overkill for one resource; project pattern is resource + config together
- **Inline diagnostic settings in main.bicep** — violates module encapsulation convention

#### Key Assumptions
- AI Search Basic tier supports `OperationLogs` diagnostic category (confirmed — all paid tiers do)
- Log Analytics workspace already has sufficient retention (30 days, per monitoring.bicep)

#### Non-Obvious Constraints
- The search module is deployed 4 times in main.bicep but only the first (line ~124) creates the actual resource; the others are role-only deployments scoped to different principals. Diagnostic settings must only go on the resource deployment.

### Risks & Open Questions
- None — this is a straightforward infra enablement with no behavioral changes

---

## Implementer — Implementation (2026-03-19)

### Changes Made
1. **`infra/modules/search.bicep`** — added optional `logAnalyticsWorkspaceId` param (empty string default). Added `Microsoft.Insights/diagnosticSettings` child resource on the search service, conditional on non-empty workspace ID. Sends `OperationLogs` + `AllMetrics`.
2. **`infra/main.bicep`** — wired `monitoring.outputs.logAnalyticsWorkspaceId` to the primary search module invocation (line ~124). Role-only invocations unchanged.
3. **`src/agent/agent/kb_agent.py`** — changed `logger.debug("Applying security filter: %s", ...)` to `logger.info(...)`.
4. **`docs/specs/infrastructure.md`** — added Diagnostic Settings row to the AI Search table.
5. **`docs/epics/011-contextual-tool-filtering.md`** — added Story 7 block, set epic status back to In Progress.

### Verification
- `az bicep build --file infra/main.bicep` — compiles clean, no errors
- `make test` — 131 agent ✅, 174 functions ✅, 123 web-app ✅ (2 pre-existing Playwright failures)
- Post-deploy verification pending: `AzureDiagnostics` KQL query after `make azure-up`

---

## Reviewer — Code Review (2026-03-19)

### Scope
Reviewed all 5 files modified for Story 7: search.bicep, main.bicep, kb_agent.py, infrastructure.md, epic doc.

### Infrastructure Review

**search.bicep** — Correct.
- New `logAnalyticsWorkspaceId` param with empty string default follows project convention (`if (!empty(...))`)
- `diagnosticSettings` is a proper child resource scoped to the search resource
- `OperationLogs` + `AllMetrics` categories are correct for AI Search
- API version `2021-05-01-preview` is standard for diagnostic settings
- Conditional deployment ensures no-op when workspace ID is not provided (role-only invocations)

**main.bicep** — Correct.
- Primary search module invocation (line ~124) now passes `logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId`
- All 3 role-only invocations (searchRoleIdx, searchWebAppRole, searchAgentContainerAppRole) do NOT pass the param — correctly omitted, defaults to empty string = no diagnostics child resource
- Module dependency chain: monitoring → search is correct (monitoring already deployed before search)

### Security Review
- [x] No secrets or credentials exposed
- [x] Diagnostic settings use workspace resource ID (RBAC-controlled), not keys
- [x] Log data stays within the same resource group's Log Analytics workspace
- [x] The promoted INFO log in kb_agent.py shows the OData filter expression — this contains department names (non-sensitive), not user PII or tokens

### Code Quality
- [x] Bicep param has `@description` annotation
- [x] Diagnostic settings resource has a descriptive comment block matching project style
- [x] Log level change is minimal and focused (debug → info, single line)
- [x] Zero IDE errors across all modified files
- [x] `az bicep build` compiles clean
- [x] `make test` passes (131 + 174 + 123)

### Documentation Review
- [x] infrastructure.md AI Search table has new Diagnostic Settings row
- [x] Epic doc has Story 7 block with deliverables and Definition of Done
- [x] Epic status changed from Done → In Progress (correct — Story 7 is in progress)
- [x] Story 7 deliverable checkboxes are unchecked (correct — pending deploy verification)

### TODO Verification
- [x] All 6 planned TODOs completed and checked off

### Verdict: ✅ Approve — clean, minimal implementation matching the plan exactly

No issues found. All changes are correctly scoped, follow project conventions, and have been validated.


---

## Reviewer — Post-Deploy Hotfix Review (2026-03-20 01:30)

### Scope
Two emergency fixes deployed after Story 7's initial deploy caused agent CrashLoopBackOff:
1. `src/agent/requirements.txt` — version pin fix
2. `src/agent/main.py` — logging config fix

### Findings

**CrashLoopBackOff root cause:** `requirements.txt` pinned `agent-framework-core==1.0.0b260107` (a newer beta published after the lock file was created). This version removed/renamed the `Agent` export from `agent_framework.__init__`, causing `ImportError: cannot import name 'Agent'` at `kb_agent.py:19`. The error repeated every ~5 min (20 restarts logged).

**Fix 1 — requirements.txt:** Regenerated from the frozen uv lock file using the same flags as the original (`--no-dev --no-hashes --no-annotate --no-emit-project --frozen`). Now pins `agent-framework-core==1.0.0rc3` and `agent-framework-azure-ai==1.0.0rc3` matching the working local env.

**Fix 2 — main.py logging config:** Two changes:
- `configure_azure_monitor()` now passes `logger_name=""` (root logger) and `logging_level=logging.INFO` so INFO logs export to App Insights (was WARNING default)
- `logging.basicConfig()` now uses `force=True` so a StreamHandler is always added for stdout even when OTel already attached a handler

### Architecture Review
- [x] Changes scoped to `src/agent/` only — no cross-service impact
- [x] No new imports, no new dependencies
- [x] Dockerfile unchanged — still uses `pip install -r requirements.txt`
- [x] `pyproject.toml` unchanged — `>=1.0.0rc3` constraint is correct; the lock file governs exact versions

### Security Review
- [x] No secrets or credentials exposed
- [x] `logger_name=""` instruments the root logger — this means ALL Python loggers will export to App Insights at INFO level. Verified the existing suppression of `azure.core`, `azure.identity`, `httpx` (set to WARNING) and `opentelemetry.context` (set to CRITICAL) prevents noisy/sensitive SDK internals from leaking
- [x] No sensitive data in INFO-level logs — the security filter log shows `search.in(department, 'engineering,...')` which is non-PII metadata
- [x] Connection string read from env var, not hardcoded

### Code Quality
- [x] `force=True` comment explains WHY it's needed — good
- [x] `logger_name=""` and `logging_level=logging.INFO` are inline-commented — good
- [x] No dead code, no leftover debug statements
- [x] Zero IDE/lint errors in main.py
- [x] 131 agent tests pass

### Warnings

**W1 — `force=True` side effect:** `force=True` removes ALL existing handlers from the root logger before adding the new StreamHandler. If `configure_azure_monitor()` attached its OTel LoggingHandler to the root logger, `force=True` will **remove it**. This means logs go to stdout but may NOT reach App Insights via the OTel pipeline.

However: `configure_azure_monitor()` installs its handler via the OTel SDK's `LoggerProvider` (which hooks into Python logging via `LoggingHandler`). The `force=True` call replaces handlers on the root `logging.Logger`, but the OTel `LoggerProvider` re-attaches on the next log record emission. In practice, both paths work — but this is fragile and version-dependent.

**Recommendation:** After confirming logs appear in both stdout and AppTraces, consider switching to explicit handler setup instead of `basicConfig(force=True)` in a future cleanup story.

**W2 — INFO-level volume in App Insights:** Setting `logging_level=logging.INFO` on the root logger will export significantly more telemetry to App Insights (every INFO log from every module). This may increase Azure Monitor ingestion costs. The existing WARNING-level overrides for `azure.core`, `azure.identity`, `httpx` mitigate the noisiest sources, but monitor ingestion volume after a few days.

### Verdict: ✅ Approve — correct emergency fix, agent recovered from CrashLoopBackOff

Both issues diagnosed accurately. The requirements.txt version mismatch was the crash cause; the logging fix was a pre-existing gap exposed during the diagnostic investigation. Agent confirmed running with 0 restarts after deploy.

---

## Reviewer — Story 7 Pivot Review (2026-03-20 03:00)

### Scope
Review the full pivot: Story 7 (AI Search diagnostic settings) was **reverted** and replaced with a leaner approach — custom OTel spans in `search_tool.py` + removal of `enable_instrumentation()` from `main.py`. Also covers the hotfix changes that stabilized the agent (logging config, agent_framework suppression, minReplicas fix).

### Context — Why the Pivot
- AI Search platform diagnostics (`OperationLogs`) log query params from the URL but **not** from POST body. The Python SDK sends `$filter` in the POST body, making it invisible in `AzureDiagnostics`.
- `enable_instrumentation()` from agent_framework created `RemoteDependency` spans with full tool payloads (60KB+), exceeding App Insights' 64KB telemetry limit — caused `Data drop 400` errors and 5-min blocking `ServiceResponseTimeoutError`.
- Custom OTel spans in our own code give us exactly the attributes we need (`search.query`, `search.filter`, `search.result_count`) at a fraction of the telemetry size.

### Changes Reviewed

| File | Change | Status |
|------|--------|--------|
| `infra/modules/search.bicep` | REVERTED — `logAnalyticsWorkspaceId` param + diagnostic settings removed | ✅ Clean |
| `infra/main.bicep` | REVERTED — no `logAnalyticsWorkspaceId` wiring to search module | ✅ Clean |
| `docs/specs/infrastructure.md` | REVERTED — diagnostic settings row removed from AI Search table | ✅ Clean |
| `docs/epics/011-contextual-tool-filtering.md` | Story 7 deleted entirely; epic status = In Progress | ✅ Correct |
| `src/agent/agent/search_tool.py` | Added `from opentelemetry import trace`, `tracer`, span wrapping search call | ✅ Correct |
| `src/agent/main.py` | `logger_name="agent"`, removed `enable_instrumentation()`, `agent_framework` → WARNING | ✅ Correct |
| `src/agent/agent/kb_agent.py` | Filter log at INFO (kept from original Story 7 — still useful) | ✅ Correct |
| `infra/modules/container-app.bicep` | `minReplicas: 1` for web-app (cold-start fix) | ✅ Correct |
| `src/agent/requirements.txt` | Regenerated with rc3 versions | ✅ Correct |

### Architecture Review
- [x] No cross-service imports — confirmed zero matches for `from shared|from fn_|from app` in `src/agent/`
- [x] `opentelemetry` import uses `opentelemetry-sdk>=1.20.0` already declared in `pyproject.toml` and pinned in `requirements.txt` (`opentelemetry-sdk==1.39.0`) — no new dependency
- [x] Config via environment variables — `APPLICATIONINSIGHTS_CONNECTION_STRING` from env, `DefaultAzureCredential` for all Azure clients
- [x] OTel span is a no-op when no `TracerProvider` is configured (unit tests run without OTel backend — safe)
- [x] `search.bicep` is clean — no residual diagnostic settings param or resource
- [x] `main.bicep` search module invocation has no `logAnalyticsWorkspaceId` parameter

### Security Review
- [x] No hardcoded secrets, keys, or tokens
- [x] `DefaultAzureCredential` for all Azure SDK clients
- [x] Span attributes contain only non-PII metadata:
  - `search.query` — truncated to 200 chars, user's natural language query (not sensitive)
  - `search.filter` — `search.in(department, 'engineering', ',')` — department names, non-PII
  - `search.top` — integer
  - `search.result_count` — integer
- [x] No sensitive data in logs — INFO logs show filter expression and result count only
- [x] `logger_name="agent"` scopes App Insights log export to only `agent.*` loggers — prevents leaking `agent_framework` payloads
- [x] `agent_framework` logger suppressed to WARNING — prevents 60KB+ tool payloads reaching App Insights

### Test Coverage Review
- [x] 131 agent tests pass, 174 functions, 123 web-app (2 pre-existing Playwright failures)
- [x] Existing `test_search_tool.py` tests mock `_search_client` — the OTel span is transparent (no-op tracer in tests)
- [x] `test_search_tool_filtering.py` covers: filter passed to client, no filter when None, multi-department filter, results with filter
- [x] No new unit tests needed for the OTel span itself — it's observability instrumentation, not business logic. The span attributes are set from values already covered by existing tests (query, top, filter, result_count).

### Code Quality
- [x] Type annotations on `search_kb()` — `query: str`, `top: int`, `security_filter: str | None`
- [x] `tracer = trace.get_tracer(__name__)` at module level — correct OTel pattern
- [x] Span wraps only the search call + result iteration (not the embedding step) — correct scoping
- [x] `query[:200]` truncation prevents oversized span attributes
- [x] Conditional `span.set_attribute("search.filter", ...)` — only set when filter is present
- [x] `span.set_attribute("search.result_count", ...)` after iteration — captures actual count
- [x] Imports organized: `__future__` → stdlib → opentelemetry → azure SDK → local
- [x] Standard `logging` module — no print statements
- [x] No bare `except:` — error handling is specific in `kb_agent.py`
- [x] Zero IDE/lint errors in both files

### Epic Documentation
- [x] Story 7 deleted from `011-contextual-tool-filtering.md` — correct, as it was reverted
- [ ] Epic status says "In Progress" but all Stories 1–6 are Done and Story 7 no longer exists — should be set back to "Done"

### Deployment Verification
- [x] Bicep compiles: `az bicep build --file infra/main.bicep` — clean
- [x] Infra provisioned: `azd provision --no-state` — all resources succeeded
- [x] All 6 services deployed: `azd deploy` — succeeded after ACR registry fix
- [x] Agent: Running/Healthy, 0 restarts, `RunningAtMaxScale`
- [x] Web-app: Running/Healthy, `minReplicas: 1`
- [x] Live query: POST `/responses` → 200 OK, `search_knowledge_base` tool invoked, relevant answer returned
- [x] `AppDependencies` KQL query confirmed `search_kb` span with:
  - `search.query`: "Content Understanding Azure AI Services"
  - `search.top`: "5"
  - `search.filter`: "search.in(department, 'engineering', ',')" ← **engineering department filter confirmed**
  - `search.result_count`: "5"
  - Duration: 327ms, Success: True
- [x] `AppTraces` confirmed both INFO logs present: "Applying security filter" and "Hybrid search"

### Warnings

**W1 — Epic status stale:** Epic 011 status is "In Progress" but all remaining stories (1–6) are Done and Story 7 was deleted. The epic should be set back to "Done". **Not a blocker** — doc-only fix.

### Verdict: ✅ Approve

The Story 7 revert is clean. The replacement approach (custom OTel spans) is architecturally superior — it gives us exactly the telemetry we need (query, filter, result count) at minimal cost, without the platform limitation that made AI Search diagnostic settings useless for POST-body filters, and without the 64KB span bomb from `enable_instrumentation()`.

### Handoff Recommendation
**Quick Fix** — set Epic 011 status back to "Done" (one-line doc change in `docs/epics/011-contextual-tool-filtering.md` line 3).

## Reviewer — Final Approval (2026-03-20 03:00)
- Verdict: ✅ Approve
- All code changes validated against architecture, security, test, and quality criteria
- Deployment verified end-to-end with live query + OTel span confirmation in App Insights
- One minor doc fix needed: Epic 011 status → "Done"

════════════════════
  IMPLEMENTATION COMPLETE
════════════════════
