---
description: "Full end-to-end local validation — clean data, setup environment, run KB pipeline, execute all tests, verify the app works locally."
agent: "implementer"
---

# End-to-End Local Test

Run a complete local environment validation: clean slate → setup → KB pipeline → tests → app verification.

## Error Recovery

If any step fails:
1. Use the `debugging` skill to trace the root cause
2. Fix the issue (code bug, config, permissions)
3. Re-run the failed step
4. If the same step fails twice after fixes, escalate to the user

## Phase 0: Discover Available Targets

Read the project `Makefile` (in the workspace root). Extract and note:

1. **Local section** — all targets between `## LOCAL-START` and `## LOCAL-END`, with their help comments
2. **Utilities — Local section** — all targets between `## UTIL-LOCAL-START` and `## UTIL-LOCAL-END`
3. **Azure section** — all targets between `## AZURE-START` and `## AZURE-END` (some Azure setup is needed for local dev)
4. **Utilities — Azure section** — all targets between `## UTIL-AZURE-START` and `## UTIL-AZURE-END`

Also read `docs/specs/architecture.md` and `docs/specs/infrastructure.md` for context.

Use the discovered target list to drive all subsequent phases. Do NOT hardcode target names.

## Phase 1: Plan

Map the discovered targets to these logical steps:

1. **Clean** — targets that clean local KB data (serving outputs, search index)
2. **Setup** — local setup target that installs tools + Python dependencies
3. **Azure Setup** — target that provisions Azure resources for local dev and configures `.env` files
4. **Enable Access** — utility targets that re-enable public access on storage/Cosmos
5. **KB Pipeline** — target that runs the full local KB pipeline (convert + index + upload)
6. **Unit Tests** — target that runs all fast tests (unit + endpoint, no Azure needed)
7. **App Verification** — targets that start the agent and web app locally

Present the plan with exact `make` commands and confirm with the user before proceeding.

## Phase 2: Clean Slate

Run the discovered clean targets to remove all local KB outputs and delete the search index.

## Phase 3: Setup Environment

### 3a — Local Tools & Dependencies
Run the local setup target to install dev tools and Python dependencies.

### 3b — Azure Resources for Local Dev
Run the Azure setup target that provisions resources and configures `.env` files.
Prerequisites: `az login` and `azd init` must have been run previously.

### 3c — Enable Access (if targets exist)
Run utility targets that re-enable public access on storage and Cosmos DB.

### 3d — Validate Infrastructure
Run any infrastructure validation target to confirm readiness.

## Phase 4: KB Pipeline

Run the full local KB pipeline target (convert HTML → Markdown, index into AI Search, upload serving assets).

## Phase 5: Run All Tests

Run the full local test suite, then individual service test targets for granular results:
- All tests combined
- Agent tests, app tests, functions tests separately

Report pass/fail counts for each. If any tests fail, trigger Error Recovery.

## Phase 6: App Smoke Test

Start the local agent and web app. Note the URLs and present them to the user for manual verification.

## Phase 7: Final Report

| Phase | Status | Details |
|-------|--------|---------|
| Clean | ✅/❌ | ... |
| Setup (local) | ✅/❌ | ... |
| Setup (Azure) | ✅/❌ | ... |
| KB Pipeline | ✅/❌ | ... |
| Tests | ✅/❌ | X passed, Y failed |
| App Smoke | ✅/❌ | URLs verified |

**Overall: PASS / FAIL**

## Rules

- **Discover targets dynamically** — read the Makefile; never hardcode target names
- **Stop on blockers** — if the same error persists after two fix attempts, escalate to the user
- **No secrets in output** — never print API keys, connection strings, or tokens
