---
description: "Full end-to-end Azure validation — clean deployed data, run KB pipeline in Azure, execute integration tests against deployed services."
agent: "implementer"
---

# End-to-End Azure Test

Run a complete Azure environment validation: clean deployed data → KB pipeline in Azure → integration tests against deployed Functions, Agent, and Web App.

## Error Recovery

If any step fails:
1. Use the `debugging` skill for first-pass diagnosis
2. Check if it's a permissions issue (403/401) → verify RBAC roles and managed identity in `infra/main.bicep`
3. Check if it's a config issue → verify `azd env get-values` and `.env` files
4. Fix and re-run the failed step
5. If the same step fails twice after fixes, escalate to the user

## Phase 0: Discover Available Targets

Read the project `Makefile` (in the workspace root). Extract and note:

1. **Azure section** — all targets between `## AZURE-START` and `## AZURE-END`
2. **Utilities — Azure section** — all targets between `## UTIL-AZURE-START` and `## UTIL-AZURE-END`
3. **Utilities — Local section** — all targets between `## UTIL-LOCAL-START` and `## UTIL-LOCAL-END` (some local utilities are needed for Azure validation)

Also read `docs/specs/architecture.md` and `docs/specs/infrastructure.md` for context.

Use the discovered target list to drive all subsequent phases. Do NOT hardcode target names.

## Phase 1: Plan

Map discovered targets to these logical steps:

1. **Validate Deployment Exists** — targets to check deployed app URL, AZD env status
2. **Clean Azure Data** — targets that clean Azure storage containers, search index, deployed analyzers
3. **KB Pipeline (Azure)** — targets that upload staging data, trigger convert, trigger index
4. **Verify Index** — targets that summarize search index contents
5. **Integration Tests** — targets that run integration tests against deployed agent and web app
6. **Health Checks** — targets for service logs, app URL, agent logs

Present the plan with exact `make` commands and confirm with the user before proceeding.

## Phase 2: Validate Deployment

1. Run `azd env get-values` to confirm environment is configured
2. Run the target that prints the deployed web app URL — verify it returns a URL
3. Verify Bicep compiles: `az bicep build --file infra/main.bicep`
4. Run `make validate-infra` if the target exists

If deployment is missing or broken, ask the user whether to run the full deploy target before continuing.

## Phase 3: Clean Azure Data

Run Azure clean targets to:
- Empty staging and serving blob containers
- Delete the AI Search index
- Delete any deployed analyzers

## Phase 4: KB Pipeline in Azure

### 4a — Upload Staging Data
Upload `kb/staging/` articles to the Azure staging blob container.

### 4b — Trigger Convert Function
Trigger the convert Azure Function (HTML → Markdown). This may take several minutes.

### 4c — Trigger Index Function
Trigger the index Azure Function (Markdown → AI Search).

### 4d — Verify Index Contents
Verify the search index was populated with the expected documents.

## Phase 5: Integration Tests

Run all Azure integration tests:
- Composite test target (all Azure tests)
- Agent integration tests (against published Foundry endpoint)
- Agent dev tests (against unpublished endpoint, if target exists)
- Web app integration tests (Cosmos + Blob + Agent)

Report pass/fail counts for each. If any fail, trigger Error Recovery.

## Phase 6: Health Checks

1. Verify web app URL is accessible (HTTP 200 or auth redirect)
2. Check app logs for exceptions/crashes
3. Check agent logs for errors

## Phase 7: Final Report

| Phase | Status | Details |
|-------|--------|---------|
| Deployment Check | ✅/❌ | Services deployed, URLs accessible |
| Clean Azure Data | ✅/❌ | Storage + index cleaned |
| Upload Staging | ✅/❌ | N articles uploaded |
| Convert Function | ✅/❌ | Function response |
| Index Function | ✅/❌ | Function response |
| Index Verification | ✅/❌ | N documents indexed |
| Agent Tests | ✅/❌ | X passed, Y failed |
| App Tests | ✅/❌ | X passed, Y failed |
| Health Checks | ✅/❌ | Services healthy/degraded |

**Overall: PASS / FAIL**

## Rules

- **Discover targets dynamically** — read the Makefile; never hardcode target names
- **Stop on blockers** — if the same error persists after two fix attempts, escalate to the user
- **No secrets in output** — never print API keys, connection strings, or tokens
- **Azure Functions may be slow** — convert and index triggers can take minutes; use generous timeouts
- **Permissions matter** — if a step fails with 403/401, check RBAC roles and managed identity config
