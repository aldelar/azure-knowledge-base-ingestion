# Epic 011 — Contextual Tool Filtering

> **Status:** Done
> **Created:** March 18, 2026
> **Updated:** March 20, 2026

## Objective

Implement **Architecture 3** from the [contextual-tool-filtering spec](../specs/contextual-tool-filtering.md) — out-of-band security context propagation from JWT claims through `ContextVar` + `FunctionMiddleware` + `**kwargs` to the `search_knowledge_base` tool, enabling department-scoped search results in Azure AI Search without the LLM ever seeing the filter.

After this epic:

- **JWT claims flow to tools without touching the LLM prompt** — the middleware extracts Entra group GUIDs from the token, resolves them to department names (simulated Graph API), and forwards enriched values to tools via `**kwargs`
- **AI Search results are department-scoped** — a new `department` field in the `kb-articles` index enables OData filtering; only articles belonging to the user's department(s) are returned
- **Tools are fully testable in isolation** — unit tests pass `departments=["engineering"]` as plain kwargs, no ContextVar, no Graph API, no running server
- **KB is organized by department** — staging articles live under `kb/staging/{department}/{article-id}/`, while the serving layer is **flat** (`{article-id}/`). The convert step writes a `metadata.json` file into each serving article folder with index-level metadata (e.g. `{"department": "engineering"}`). The indexer reads `metadata.json` to populate search index fields — it has no knowledge of the staging folder structure.
- **Dev mode works without auth** — when `REQUIRE_AUTH=false`, the middleware sets default dev claims (`department=engineering`) so local development doesn't require a JWT
- **E2E tests validate filters are applied** — end-to-end tests confirm that department filtering actually restricts search results

## Success Criteria

- [x] `kb/staging/` reorganized into `kb/staging/engineering/{article-id}/` structure
- [x] Serving layer is flat `{article-id}/` with a `metadata.json` file containing department and other index metadata
- [x] `kb-articles` index has a `department` field (string, filterable)
- [x] `fn-convert` writes `metadata.json` with `department` derived from the staging folder path
- [x] `fn-index` reads `metadata.json` and populates index fields accordingly
- [x] `make index` re-indexes successfully with the new field populated
- [x] `middleware/request_context.py` defines `user_claims_var` and `resolved_departments_var` ContextVars
- [x] `JWTAuthMiddleware` extracts claims into `user_claims_var`; sets default dev claims when auth is disabled
- [x] `agent/group_resolver.py` provides a simulated resolver returning `["engineering"]`
- [x] `SecurityFilterMiddleware` resolves groups once and writes enriched values to `context.kwargs`
- [x] `search_knowledge_base` accepts `**kwargs`, builds OData filter from `departments`, passes it to `search_kb()`
- [x] `search_kb()` passes `filter=` parameter to Azure AI Search
- [x] Unit tests prove the tool is testable with plain kwargs (no ContextVar, no Graph API)
- [x] Integration test proves department filter restricts AI Search results
- [x] E2E test validates the full chain: request with claims → agent → filtered search results
- [x] `make test` passes with zero regressions
- [x] Spec and architecture docs updated

---

## Background

See [docs/specs/contextual-tool-filtering.md](../specs/contextual-tool-filtering.md) for the full research and architecture comparison.

### Current vs. Proposed

| Aspect | Current | After Epic 011 |
|--------|---------|----------------|
| JWT claims | Validated for auth, then discarded | Extracted into `ContextVar`, resolved by middleware |
| Group → department resolution | N/A | Simulated resolver (swappable for real Graph API later) |
| Tool receives security context | No — only LLM-provided `query` | Yes — `departments`, `roles`, `tenant_id` via `**kwargs` |
| AI Search filtering | No filter — all articles returned | `department` OData filter — scoped to user's department(s) |
| KB staging layout | Flat `kb/staging/{article-id}/` | `kb/staging/{department}/{article-id}/` |
| Serving layer layout | Flat `{article-id}/` | Flat `{article-id}/` with `metadata.json` (department is metadata, not a folder) |
| Tool testability | Tool imports module-level clients, hard to unit test | Tool accepts `**kwargs`, testable with plain Python args |

---

### Story 1 — KB Reorganization + Index Department Field ✅

> **Status:** Done
> **Depends on:** None

Reorganize the KB staging folder to `kb/staging/{department}/{article-id}/`, keep the serving layer flat (`{article-id}/`), add a `department` field to the AI Search index, and update the pipeline so `fn-convert` writes a `metadata.json` file (containing `department` and any future index fields) into each serving article folder. `fn-index` reads `metadata.json` and populates index fields accordingly. Re-index to populate the new field.

#### Deliverables

- [x] Move existing articles under `kb/staging/engineering/` (e.g., `kb/staging/engineering/agentic-retrieval-overview-html_en-us/`)
- [x] Update `fn-convert` to write serving output to flat `{article-id}/` path and generate `metadata.json` with `{"department": "..."}` derived from the staging folder structure
- [x] Add `department` field (type: `Edm.String`, filterable: true) to the index schema in `src/functions/fn_index/indexer.py`
- [x] Update `fn-index` to read `metadata.json` from each article folder and use its fields to populate the search index
- [x] Update any Makefile targets (`convert`, `index`) that reference the old flat path structure
- [x] Re-index with `make index` — verify `department=engineering` is populated on all documents

#### Implementation Notes

- The serving layer is flat: `{article-id}/article.md` + `{article-id}/metadata.json` + `{article-id}/images/`. Department is stored as metadata, not as a folder.
- `fn-convert` reads from staging `{department}/{article-id}/`, writes to serving `{article-id}/`, and generates `metadata.json` as the contract between convert and index.
- `fn-index` reads `metadata.json` and maps its keys directly to AI Search index fields. Adding a new filterable dimension only requires `fn-convert` to write an additional field.
- The `article_id` in the index remains the article folder name. The `department` is a separate filterable field.

#### Definition of Done

- [x] `ls kb/staging/engineering/` shows all 3 existing articles
- [x] `make convert analyzer=markitdown` produces output under `kb/serving/engineering/{article-id}/`
- [x] `make index` completes without errors
- [x] Azure AI Search explorer query confirms `department` field is `"engineering"` on all indexed documents
- [x] `make test-functions` passes with zero regressions

---

### Story 2 — ContextVar + JWT Claims Extraction ✅

> **Status:** Done
> **Depends on:** None (parallel with Story 1)

Create the `ContextVar` infrastructure and extend the JWT middleware to extract claims into it. Provide default dev claims when auth is disabled.

#### Deliverables

- [x] Create `src/agent/middleware/request_context.py` with:
  - `user_claims_var: ContextVar[dict]` (default: `{}`)
  - `resolved_departments_var: ContextVar[list[str]]` (default: `[]`)
- [x] Extend `JWTAuthMiddleware.dispatch()` to set `user_claims_var` with decoded claims (`oid`, `tid`, `groups`, `roles`) after successful token validation
- [x] When `REQUIRE_AUTH=false`, set default dev claims: `{"user_id": "dev-user", "tenant_id": "dev-tenant", "groups": ["dev-group-guid"], "roles": ["contributor"]}`
- [x] Create `src/agent/agent/group_resolver.py` with a simulated `resolve_departments(group_guids: list[str]) -> list[str]` that returns `["engineering"]` for any non-empty input

#### Implementation Notes

- Follow the existing middleware pattern in `middleware/jwt_auth.py`. The ContextVar is set inside `dispatch()` — Python's `contextvars` automatically scopes it to the current async task.
- The dev claims default should be clearly visible in the code (not hidden in config) so developers understand what context the tools will receive.
- `group_resolver.py` is intentionally simple — it's a placeholder for real Graph API integration in a future epic.

#### Definition of Done

- [x] `from middleware.request_context import user_claims_var, resolved_departments_var` works from any module in `src/agent/`
- [x] With `REQUIRE_AUTH=false`, a request to `/responses` results in `user_claims_var.get()` returning the dev claims dict
- [x] `resolve_departments(["any-guid"])` returns `["engineering"]`
- [x] `make test` passes with zero regressions

---

### Story 3 — SecurityFilterMiddleware + Tool Wiring ✅

> **Status:** Done
> **Depends on:** Story 1 ✅, Story 2 ✅

Create the `FunctionMiddleware` that resolves groups once per request and writes enriched values to `context.kwargs`. Update `search_knowledge_base` to accept `**kwargs` and build an OData filter. Wire middleware into the agent.

#### Deliverables

- [x] Create `src/agent/agent/security_middleware.py` with `SecurityFilterMiddleware(FunctionMiddleware)`:
  - Reads `user_claims_var` to get raw claims
  - Calls `resolve_departments(groups)` once
  - Writes `departments`, `roles`, `tenant_id` to `context.kwargs`
- [x] Update `search_knowledge_base()` in `agent/kb_agent.py`:
  - Add `**kwargs` to signature
  - Read `departments = kwargs.get("departments", [])`
  - Build OData filter: `search.in(department, 'engineering,...')` if departments present
  - Pass filter to `search_kb(query, security_filter=odata_filter)`
- [x] Update `search_kb()` in `agent/search_tool.py`:
  - Add `security_filter: str | None = None` parameter
  - Pass `filter=security_filter` to `_search_client.search()`
- [x] Register `SecurityFilterMiddleware` on the agent in `agent/kb_agent.py` → `create_agent()`
- [x] Update `src/agent/.env.sample` with any new env vars if needed

#### Implementation Notes

- The middleware knows nothing about OData or AI Search — it just resolves group GUIDs to department names and passes them through. The tool owns the filter syntax.
- The `search.in()` OData function is the correct way to filter on a string field with multiple values in Azure AI Search.
- The `**kwargs` on the tool function causes the Agent Framework to auto-detect `_forward_runtime_kwargs = True` — no manual configuration needed.

#### Definition of Done

- [x] `SecurityFilterMiddleware` is registered on the agent and runs before every tool call
- [x] In dev mode (no auth), a search query produces results filtered to `department eq 'engineering'` (visible in agent logs)
- [x] `search_kb(query, security_filter="department eq 'engineering'")` correctly passes the filter to Azure AI Search
- [x] Agent still works end-to-end: ask a question → get a filtered, cited answer
- [x] `make test` passes with zero regressions

---

### Story 4 — Unit Tests (Tool Testability) ✅

> **Status:** Done
> **Depends on:** Story 3 ✅

Prove the Architecture 3 value proposition: tools are testable in complete isolation — pass `departments=["engineering"]` as plain kwargs, no ContextVar, no Graph API, no running server.

#### Deliverables

- [x] Create `src/agent/tests/test_search_tool_filtering.py` with unit tests:
  - `test_build_odata_filter_single_department` — pass `departments=["engineering"]`, verify OData filter string is `"department eq 'engineering'"`
  - `test_build_odata_filter_multiple_departments` — pass `departments=["engineering", "research"]`, verify `search.in(department, 'engineering,research')`
  - `test_build_odata_filter_empty_departments` — pass `departments=[]`, verify no filter applied (None)
  - `test_search_kb_passes_filter` — mock `_search_client.search()`, call `search_kb(query, security_filter="department eq 'engineering'")`, assert `filter=` kwarg was passed to the mock
  - `test_tool_callable_with_plain_kwargs` — call `search_knowledge_base("test query", departments=["engineering"])` with mocked search client, verify it runs without ContextVar or middleware
- [x] Create `src/agent/tests/test_security_middleware.py` with unit tests:
  - `test_middleware_resolves_departments` — set `user_claims_var` with test groups, run middleware, assert `context.kwargs["departments"]` is populated
  - `test_middleware_empty_groups` — set claims with no groups, assert `departments` is `[]`
  - `test_middleware_passes_roles_and_tenant` — verify roles and tenant_id are forwarded
- [x] Create `src/agent/tests/test_group_resolver.py`:
  - `test_resolve_returns_engineering` — `resolve_departments(["any-guid"])` returns `["engineering"]`
  - `test_resolve_empty_input` — `resolve_departments([])` returns `[]`

#### Implementation Notes

- The key insight: `search_knowledge_base("query", departments=["engineering"])` is a valid direct call — no Agent Framework, no HTTP server, no ContextVar needed. This is the whole point of Architecture 3.
- Use `unittest.mock.patch` to mock `_search_client` and `_embeddings_client` in the search tool module.
- Follow existing test patterns in `src/agent/tests/`.

#### Definition of Done

- [x] `cd src/agent && uv run pytest tests/test_search_tool_filtering.py -v` — all 5 tests pass
- [x] `cd src/agent && uv run pytest tests/test_security_middleware.py -v` — all 3 tests pass
- [x] `cd src/agent && uv run pytest tests/test_group_resolver.py -v` — all 2 tests pass
- [x] `make test` passes with zero regressions (total test count increases by 10)

---

### Story 5 — Integration + E2E Tests ✅

> **Status:** Done
> **Depends on:** Story 3 ✅, Story 4 ✅

Prove the full chain works end-to-end: JWT claims → ContextVar → middleware → tool → filtered AI Search results. Integration tests hit real AI Search; E2E tests validate the complete request lifecycle.

#### Deliverables

- [x] Create `src/agent/tests/test_department_filter_integration.py` (marked `@pytest.mark.integration`):
  - `test_search_with_engineering_filter` — call `search_kb("azure search", security_filter="department eq 'engineering'")` against real AI Search, verify all returned results have `department == "engineering"`
  - `test_search_without_filter` — call `search_kb("azure search")` with no filter, verify results are returned (baseline)
  - `test_search_with_nonexistent_department` — call with `security_filter="department eq 'nonexistent'"`, verify zero results
- [x] Create `src/agent/tests/test_contextual_filtering_e2e.py` (marked `@pytest.mark.integration`):
  - `test_e2e_dev_mode_applies_filter` — with `REQUIRE_AUTH=false`, send a request through the full agent stack (HTTP → middleware → agent → tool → AI Search), verify response contains only engineering-department articles
  - `test_e2e_filter_visible_in_logs` — verify the OData filter expression appears in agent logs (confirms the filter was applied, not silently dropped)

#### Implementation Notes

- Integration tests require `SEARCH_ENDPOINT` and `AI_SERVICES_ENDPOINT` env vars (same as existing integration tests).
- E2E tests can use `httpx.AsyncClient` against the Starlette app (same pattern as testing `/responses` endpoint).
- The dev mode default claims ensure the filter is always applied even without a JWT — this is the simplest way to test the full chain locally.

#### Definition of Done

- [x] `cd src/agent && uv run pytest tests/test_department_filter_integration.py -v -m integration` — all 3 tests pass against real AI Search
- [x] `cd src/agent && uv run pytest tests/test_contextual_filtering_e2e.py -v -m integration` — all 2 tests pass
- [x] Tests confirm: with `department eq 'engineering'` filter, only engineering articles are returned; with `department eq 'nonexistent'`, zero results
- [x] `make test` (unit tests only) still passes with zero regressions

---

### Story 6 — Documentation & Cleanup ✅

> **Status:** Done
> **Depends on:** Story 5 ✅

Update all documentation to reflect the new contextual filtering architecture. Add Core Pattern 8 to the README with Architecture 3 diagram and link to the spec.

#### Deliverables

- [x] **`README.md` — add Core Pattern 8: Contextual Tool Filtering**
  - Update the intro line from "seven architectural patterns" to "eight architectural patterns"
  - Add a new `### 8. Contextual Tool Filtering` section after Pattern 7, following the same format (Problem / Pattern / diagram / link)
  - **Problem:** Agent tools query backends (AI Search, databases) but have no way to apply per-user security filters without leaking identity context into the LLM prompt
  - **Pattern:** Three-layer out-of-band propagation (ContextVar → FunctionMiddleware → `**kwargs`) using the Microsoft Agent Framework. JWT claims are extracted at the HTTP boundary, enriched by a middleware that resolves group GUIDs to department names (Graph API), and forwarded to tools as plain kwargs. Tools build backend-specific filters (OData, SQL) from the enriched values. The LLM never sees the filter context. Tools are testable in isolation by passing kwargs directly.
  - Include a Mermaid diagram showing the Architecture 3 flow (HTTP Request → JWT Middleware → Agent Framework → FunctionMiddleware → Graph API → Tool with `**kwargs` + Unit Test bypass)
  - Link to the full spec: `docs/specs/contextual-tool-filtering.md`
- [x] **`docs/specs/architecture.md`** — add a section on out-of-band context propagation (ContextVar → middleware → kwargs → tool filter), reference the spec and README pattern
- [x] **`docs/specs/contextual-tool-filtering.md`** — add "Implementation Status" section noting Epic 011 implemented Architecture 3 with simulated Graph API resolver, department field in AI Search index, and KB reorganized by department
- [x] **`src/agent/.env.sample`** — document any new env vars
- [x] **`README.md` KB section** — verify it reflects the new `kb/staging/{department}/` layout
- [x] **Review other docs for staleness:**
  - `docs/specs/infrastructure.md` — check if the AI Search index field list needs updating (new `department` field)
  - `docs/setup-and-makefile.md` — check if any Makefile target documentation needs updating for the new folder structure
  - `docs/epics/001-local-pipeline-e2e.md` — check if the KB folder structure references need a note
- [x] **Update this epic file** — mark all stories as Done, set epic status to Done

#### Implementation Notes

- The README Core Pattern format is: heading, **Problem** paragraph, **Pattern** paragraph(s), Mermaid diagram, optional table, horizontal rule. See Patterns 1–7 for exact formatting.
- The Architecture 3 diagram for the README should be the same as the one in the spec (Architecture 3 section) — with the Graph API node on the middleware, Unit Test bypass arrows to the tool, and the four color scheme (green/orange/blue/purple).
- Keep the README pattern concise — 2–3 paragraphs max. The spec has the full detail; the README links to it.

#### Definition of Done

- [x] `README.md` contains `### 8. Contextual Tool Filtering` with Problem, Pattern, and Mermaid diagram
- [x] `README.md` intro says "eight architectural patterns"
- [x] `docs/specs/architecture.md` mentions contextual tool filtering and references the spec
- [x] `docs/specs/contextual-tool-filtering.md` has an "Implementation Status" section
- [x] `.env.sample` is current
- [x] All other docs reviewed and updated if stale
- [x] All stories in this epic are marked Done
- [x] `git diff --stat` shows no untracked or uncommitted changes related to this epic
