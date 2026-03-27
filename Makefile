.DEFAULT_GOAL := help

DEV_ENV_FILE ?= .env.dev
DEV_INFRA_PROJECT := kb-agent-infra
DEV_SERVICES_PROJECT := kb-agent-services
DEV_INFRA_COMPOSE := docker compose -p $(DEV_INFRA_PROJECT) --env-file $(DEV_ENV_FILE) -f docker-compose.dev-infra.yml
DEV_SERVICES_COMPOSE := docker compose -p $(DEV_SERVICES_PROJECT) --env-file $(DEV_ENV_FILE) -f docker-compose.dev-services.yml
CONVERTER ?= $(shell azd env get-value CONVERTER 2>/dev/null || echo markitdown)

.PHONY: help
help:
	@echo ""
	@echo "Dev"
	@echo "  make dev-setup                Install tools and Python dependencies as your normal user"
	@echo "  sudo make dev-setup-gpu       Configure Docker GPU support for a local Linux Docker engine"
	@echo "  make dev-infra-up             Start local emulators and initialize resources"
	@echo "  make dev-infra-down           Stop local emulators"
	@echo "  make dev-services-up          Build and start the full local application stack"
	@echo "  make dev-services-down        Stop local application services"
	@echo "  make dev-services-pipeline-up Build and start fn-convert + fn-index"
	@echo "  make dev-services-app-up      Build and start the web app"
	@echo "  make dev-services-agents-up   Build and start the agent"
	@echo "  make dev-seed-kb              Sync kb/staging into local Azurite staging"
	@echo "  make dev-test                 Run unit + integration tests"
	@echo "  make dev-test-ui              Run optional browser UI tests"
	@echo "  make dev-ui                   Print the local UI URL"
	@echo "  make dev-pipeline             Run local convert + index pipeline"
	@echo "  make dev-pipeline-convert     Trigger local MarkItDown convert"
	@echo "  make dev-pipeline-index       Trigger local indexing"
	@echo ""
	@echo "Prod"
	@echo "  make prod-infra-up            Provision Azure infrastructure with AZD"
	@echo "  make prod-infra-down          Delete Azure infrastructure with confirmation"
	@echo "  make prod-services-up         Deploy app, agent, fn-index, and selected converter"
	@echo "  make prod-services-down       Print scale-down guidance for deployed services"
	@echo "  make prod-services-pipeline-up Deploy pipeline services only"
	@echo "  make prod-services-app-up     Deploy the web app only"
	@echo "  make prod-services-agents-up  Deploy the agent only"
	@echo "  make prod-ui-url              Print the production web app URL"
	@echo "  make prod-pipeline            Run Azure convert + index pipeline"
	@echo "  make prod-pipeline-convert    Trigger the selected Azure converter"
	@echo "  make prod-pipeline-index      Trigger Azure indexing"
	@echo ""
	@echo "Shared"
	@echo "  make set-project name=<id>    Set PROJECT_NAME in the active AZD environment"
	@echo "  make set-converter name=<name> Set CONVERTER to cu, markitdown, or mistral"

.PHONY: dev-setup
dev-setup:
	@if [ $$(id -u) -eq 0 ] || [ -n "$${SUDO_USER:-}" ]; then \
		echo "Run make dev-setup as your normal user." >&2; \
		echo "Use sudo make dev-setup-gpu only for Docker GPU runtime setup." >&2; \
		exit 1; \
	fi
	@bash scripts/dev-setup.sh
	@cd src/functions && uv sync --extra dev
	@cd src/agent && uv sync --extra dev
	@cd src/web-app && uv sync --extra dev
	@if [ ! -f $(DEV_ENV_FILE) ]; then \
		echo "Copy .env.dev.template to $(DEV_ENV_FILE) before starting the local stack."; \
	fi

.PHONY: dev-setup-gpu
dev-setup-gpu:
	@if [ $$(id -u) -ne 0 ] && [ -z "$${SUDO_USER:-}" ]; then \
		echo "Run sudo make dev-setup-gpu." >&2; \
		exit 1; \
	fi
	@bash scripts/dev-setup-gpu.sh

.PHONY: dev-infra-up
dev-infra-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_INFRA_COMPOSE) up -d
	@bash scripts/dev-init-emulators.sh

.PHONY: dev-infra-down
dev-infra-down:
	@$(DEV_INFRA_COMPOSE) down

.PHONY: dev-services-up
dev-services-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_SERVICES_COMPOSE) up -d --build

.PHONY: dev-services-down
dev-services-down:
	@$(DEV_SERVICES_COMPOSE) stop fn-convert fn-index agent web-app

.PHONY: dev-services-pipeline-up
dev-services-pipeline-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_SERVICES_COMPOSE) up -d --build fn-convert fn-index

.PHONY: dev-services-app-up
dev-services-app-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_SERVICES_COMPOSE) up -d --build web-app

.PHONY: dev-services-agents-up
dev-services-agents-up:
	@test -f $(DEV_ENV_FILE) || (echo "Missing $(DEV_ENV_FILE). Copy .env.dev.template first." >&2; exit 1)
	@$(DEV_SERVICES_COMPOSE) up -d --build agent

.PHONY: dev-test
dev-test:
	@cd src/functions && uv run pytest tests -o addopts= -m "not uitest"
	@cd src/agent && uv run pytest tests -o addopts= -m "not uitest"
	@cd src/web-app && uv run pytest tests -o addopts= -m "not uitest"

.PHONY: dev-seed-kb
dev-seed-kb:
	@bash scripts/dev-seed-kb.sh

.PHONY: dev-test-ui
dev-test-ui:
	@cd src/web-app && uv run pytest tests -o addopts= -m uitest

.PHONY: dev-ui
dev-ui:
	@echo http://localhost:8080

.PHONY: dev-pipeline
dev-pipeline: dev-pipeline-convert dev-pipeline-index

.PHONY: dev-pipeline-convert
dev-pipeline-convert:
	@$(MAKE) dev-seed-kb
	@curl -fsS -X POST http://localhost:7071/api/convert-markitdown -H 'Content-Type: application/json' -d '{}'

.PHONY: dev-pipeline-index
dev-pipeline-index:
	@curl -fsS -X POST http://localhost:7072/api/index -H 'Content-Type: application/json' -d '{}'

.PHONY: prod-infra-up
prod-infra-up:
	@azd provision

.PHONY: prod-infra-down
prod-infra-down:
	@printf "Delete the active Azure environment? [y/N] " && read answer && [ "$$answer" = "y" ]
	@azd down --force --purge

.PHONY: prod-services-up
prod-services-up: prod-services-app-up prod-services-agents-up prod-services-pipeline-up

.PHONY: prod-services-down
prod-services-down:
	@echo "Scale-down remains environment-specific. Use Azure CLI or the portal to reduce replicas to zero for deployed Container Apps."

.PHONY: prod-services-pipeline-up
prod-services-pipeline-up:
	@azd deploy --service func-index
	@case "$(CONVERTER)" in \
		cu) azd deploy --service func-convert-cu ;; \
		mistral) azd deploy --service func-convert-mistral ;; \
		markitdown) azd deploy --service func-convert-markitdown ;; \
		*) echo "Unsupported CONVERTER=$(CONVERTER). Use cu, markitdown, or mistral." >&2; exit 1 ;; \
	 esac

.PHONY: prod-services-app-up
prod-services-app-up:
	@azd deploy --service web-app

.PHONY: prod-services-agents-up
prod-services-agents-up:
	@azd deploy --service agent

.PHONY: prod-ui-url
prod-ui-url:
	@azd env get-value WEBAPP_URL

.PHONY: prod-pipeline
prod-pipeline: prod-pipeline-convert prod-pipeline-index

.PHONY: prod-pipeline-convert
prod-pipeline-convert:
	@case "$(CONVERTER)" in \
		cu) curl -fsS -X POST "$$(azd env get-value SERVICE_FUNC_CONVERT_CU_ENDPOINT)/api/convert" -H 'Content-Type: application/json' -d '{}' ;; \
		mistral) curl -fsS -X POST "$$(azd env get-value SERVICE_FUNC_CONVERT_MISTRAL_ENDPOINT)/api/convert-mistral" -H 'Content-Type: application/json' -d '{}' ;; \
		markitdown) curl -fsS -X POST "$$(azd env get-value SERVICE_FUNC_CONVERT_MARKITDOWN_ENDPOINT)/api/convert-markitdown" -H 'Content-Type: application/json' -d '{}' ;; \
		*) echo "Unsupported CONVERTER=$(CONVERTER). Use cu, markitdown, or mistral." >&2; exit 1 ;; \
	 esac

.PHONY: prod-pipeline-index
prod-pipeline-index:
	@curl -fsS -X POST "$$(azd env get-value SERVICE_FUNC_INDEX_ENDPOINT)/api/index" -H 'Content-Type: application/json' -d '{}'

.PHONY: set-project
set-project:
	@if [ -z "$(name)" ]; then echo "Usage: make set-project name=<id>" >&2; exit 1; fi
	@azd env set PROJECT_NAME "$(name)"

.PHONY: set-converter
set-converter:
	@if [ -z "$(name)" ]; then echo "Usage: make set-converter name=<cu|markitdown|mistral>" >&2; exit 1; fi
	@case "$(name)" in cu|markitdown|mistral) ;; *) echo "Use cu, markitdown, or mistral." >&2; exit 1 ;; esac
	@azd env set CONVERTER "$(name)"