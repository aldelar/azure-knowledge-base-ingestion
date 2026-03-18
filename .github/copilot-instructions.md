# Copilot Instructions

## Project

**Context Aware & Vision Grounded KB Agent** — an Azure-hosted two-stage pipeline that transforms HTML knowledge base articles into an AI-searchable index with image support, fronted by a conversational agent.

- **Stack:** Python 3.11+, Azure (Bicep + AZD), pytest, uv
- **Architecture:** See `docs/specs/architecture.md`
- **Infrastructure:** See `docs/specs/infrastructure.md`
- **Setup & Automation:** See `docs/setup-and-makefile.md` or run `make help`

## Solution Structure

- `src/agent/` — Foundry hosted KB Agent (FastAPI + Agent Framework)
- `src/functions/` — Azure Functions: `fn-convert` (HTML→Markdown) + `fn-index` (Markdown→AI Search)
- `src/web-app/` — Chainlit thin client (OpenAI SDK + Cosmos DB data layer)
- `infra/` — Bicep modules for all Azure resources
- `docs/epics/` — Epic and story tracking (source of truth for work status)
- `scripts/` — Automation and setup scripts

## Key Conventions

- **Infrastructure as Code only** — no manual Azure portal changes
- **Managed identity everywhere** — no keys or secrets in code or config
- **Environment-driven config** — `.env` files from `azd env get-values`, never hardcoded
- **uv** for Python dependency management — each service has its own `pyproject.toml`
- **Tests before commit** — run `make test` to validate all services
- **Docs match code** — epic docs must always reflect the actual implementation state

## Agent-Driven Development

This repo uses a **3-agent handoff model** with skills, instructions, and prompts for structured development:

### Agents (`.github/agents/`)

| Agent | Role | Handoffs |
|-------|------|----------|
| **@planner** | Research codebase, produce plans, create scratchpads and TODOs. Never writes code. | → @implementer, → @reviewer |
| **@implementer** | Write code, manage infra (Bicep/AZD), run tests, debug failures, update epic docs. Full edit + terminal access. | → @reviewer, → @planner |
| **@reviewer** | Code review for architecture, security, tests, quality. Never writes code. | → @implementer (fix/rework), → @planner (re-plan) |

### Shared Scratchpad Protocol

Agents persist context across handoffs via append-only scratchpad files in `shared-scratchpads/`:
- **Planner creates** a scratchpad as their first action in every session
- **All agents append** before every handoff — timestamped entries with decisions, constraints, findings
- **Reviewer closes** with `IMPLEMENTATION COMPLETE` marker on final approval
- See [shared-scratchpad.instructions.md](instructions/shared-scratchpad.instructions.md) for the full protocol

### Skills (`.github/skills/`)

Domain-specific knowledge loaded on demand by agents:
- `debugging` — Structured first-pass debugging for test failures and runtime errors
- `architecture-check` — Service boundary validation (agent/functions/web-app/infra isolation)
- `security-review` — Azure-specific security checklist (managed identity, RBAC, secrets, input validation)
- `epic-workflow` — Epic/story lifecycle management with project-specific make targets
- `azure-infra-review` — Bicep module review (naming, RBAC, wiring, doc sync)
- `refactoring` — Safe refactoring across the service-based architecture

### Instructions (`.github/instructions/`)

Composable rules auto-applied by file pattern:
- [python-standards.instructions.md](instructions/python-standards.instructions.md) — Python/uv/Azure SDK conventions (`src/**/*.py`)
- [testing.instructions.md](instructions/testing.instructions.md) — pytest three-tier test strategy (`**/tests/**`)
- [security.instructions.md](instructions/security.instructions.md) — Secrets, auth, and validation rules (`**`)
- [epic-tracking.instructions.md](instructions/epic-tracking.instructions.md) — Epic lifecycle and doc-code consistency (`docs/epics/**`)
- [azure-infra.instructions.md](instructions/azure-infra.instructions.md) — Bicep modules and AZD deployment (`infra/**`)
- [shared-scratchpad.instructions.md](instructions/shared-scratchpad.instructions.md) — Cross-agent scratchpad protocol (`shared-scratchpads/**`)

### Prompts (`.github/prompts/`)

Reusable workflows for common development tasks:
- `deliver-epic` / `deliver-story` — End-to-end story and epic delivery via handoff workflow
- `write-epic` / `write-story` — Collaborative epic/story authoring
- `write-tests` — Test generation for a module
- `pre-commit-check` — Pre-commit quality validation
- `deploy-check` / `post-deploy-verify` — Deployment readiness and post-deploy health
- `test-e2e-local` / `test-e2e-azure` — Full end-to-end validation (local and Azure)