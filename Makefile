# Context Aware & Vision Grounded KB Agent — Makefile
# ==============================================================================
# Targets for local development, Azure provisioning, and pipeline execution.
#
# Local targets use kb/staging/ (source articles) and kb/serving/ (processed output).
# Azure targets operate against deployed Azure resources via AZD.
# ==============================================================================

# Discover articles in local staging folder
STAGING_ARTICLES := $(notdir $(wildcard kb/staging/*))

.DEFAULT_GOAL := help

# ------------------------------------------------------------------------------
# Help
# ------------------------------------------------------------------------------
.PHONY: help
help: ## Show available targets
	@echo ""
	@echo "  Local Development"
	@echo "  ─────────────────"
	@grep -E '^(dev-|convert|index|test|validate|grant|app|agent)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-44s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Azure Operations"
	@echo "  ─────────────────"
	@grep -E '^azure-[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "    \033[36m%-44s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ------------------------------------------------------------------------------
# Local Development — Prerequisites
# ------------------------------------------------------------------------------
.PHONY: dev-doctor dev-setup dev-setup-env

dev-doctor: ## Check if required dev tools are installed
	@echo "Checking development prerequisites...\n"
	@status=0; \
	for cmd in az azd uv python3 func; do \
		printf "  %-12s" "$$cmd"; \
		if command -v $$cmd >/dev/null 2>&1; then \
			if [ "$$cmd" = "azd" ]; then \
				version=$$($$cmd version 2>&1 | head -1); \
			else \
				version=$$($$cmd --version 2>&1 | head -1); \
			fi; \
			printf "\033[32m✔\033[0m  $$version\n"; \
		else \
			printf "\033[31m✘  not found\033[0m\n"; \
			status=1; \
		fi; \
	done; \
	echo ""; \
	if [ $$status -eq 0 ]; then \
		echo "\033[32mAll prerequisites met.\033[0m"; \
	else \
		echo "\033[31mSome tools are missing. Run 'make dev-setup' to install.\033[0m"; \
	fi

dev-setup: ## Install required dev tools and Python dependencies
	@bash scripts/dev-setup.sh
	@echo ""
	@echo "Installing Python dependencies (functions)..."
	@cd src/functions && uv sync --extra dev
	@echo "Installing Python dependencies (web app)..."
	@cd src/web-app && uv sync --extra dev
	@echo "Installing Python dependencies (agent)..."
	@cd src/agent && uv sync --extra dev
	@echo "Python dependencies installed."

dev-setup-env: ## Populate .env files from AZD environment (functions + web app + agent)
	@echo "Writing AZD environment values to src/functions/.env..."
	@azd env get-values > src/functions/.env
	@echo "Done. $(shell wc -l < src/functions/.env 2>/dev/null || echo 0) variables written."
	@echo "Writing AZD environment values to src/web-app/.env..."
	@azd env get-values > src/web-app/.env
	@echo "Done. $(shell wc -l < src/web-app/.env 2>/dev/null || echo 0) variables written."
	@echo "Writing AZD environment values to src/agent/.env..."
	@azd env get-values > src/agent/.env
	@echo "Done. $(shell wc -l < src/agent/.env 2>/dev/null || echo 0) variables written."

# ------------------------------------------------------------------------------
# Local Development — Storage Access
# ------------------------------------------------------------------------------
.PHONY: dev-enable-storage dev-enable-cosmos

dev-enable-storage: ## Re-enable public access on storage accounts (disabled nightly)
	@bash scripts/enable-storage-public-access.sh

dev-enable-cosmos: ## Enable public access on Cosmos DB + add developer IP to firewall
	@bash scripts/enable-cosmos-public-access.sh

# ------------------------------------------------------------------------------
# Local Development — Pipeline
# ------------------------------------------------------------------------------
.PHONY: convert index test validate-infra

test: test-agent test-app ## Run all fast tests (unit + endpoint, no Azure needed)
	@cd src/functions && uv run pytest tests/ -v || test $$? -eq 5

validate-infra: ## Validate Azure infra is ready for local dev
	@bash scripts/functions/validate-infra.sh

convert: ## Run fn-convert locally (analyzer=content-understanding|mistral-doc-ai)
ifndef analyzer
	@echo "Error: analyzer is required. Usage:" >&2
	@echo "  make convert analyzer=content-understanding" >&2
	@echo "  make convert analyzer=mistral-doc-ai" >&2
	@exit 1
endif
	@bash scripts/functions/convert.sh $(analyzer)

index: ## Run fn-index locally (kb/serving → Azure AI Search)
	@bash scripts/functions/index.sh

# ------------------------------------------------------------------------------
# Local Development — Web App
# ------------------------------------------------------------------------------
.PHONY: app test-app

app: ## Run Context Aware & Vision Grounded KB Agent locally (http://localhost:8080)
	@cd src/web-app && uv run chainlit run app/main.py -w --port 8080

test-app: ## Run web app unit tests (no Azure needed)
	@cd src/web-app && uv run pytest tests/ -v -m "not integration" || test $$? -eq 5

# ------------------------------------------------------------------------------
# Local Development — Agent
# ------------------------------------------------------------------------------
.PHONY: agent test-agent test-agent-integration

agent: ## Run KB Agent locally (http://localhost:8088)
	@cd src/agent && uv run python main.py

test-agent: ## Run agent unit + endpoint tests (no Azure needed)
	@cd src/agent && uv run pytest tests/ -v -m "not integration" || test $$? -eq 5

test-agent-integration: ## Run agent integration tests (needs running local agent)
	@cd src/agent && AGENT_ENDPOINT=http://localhost:8088 uv run pytest tests/ -v -m integration || test $$? -eq 5

# ------------------------------------------------------------------------------
# Local Development — RBAC
# ------------------------------------------------------------------------------
.PHONY: grant-dev-roles

grant-dev-roles: ## Grant Cosmos DB native RBAC to current developer + verify ARM roles
	@echo "Granting developer RBAC roles..."
	@echo ""
	@set -a && . src/functions/.env && set +a && \
	USER_OID=$$(az ad signed-in-user show --query id -o tsv) && \
	echo "  User: $$USER_OID" && \
	echo "" && \
	ENV=$$(azd env get-value AZURE_ENV_NAME 2>/dev/null || echo "dev") && \
	COSMOS_ACCOUNT="cosmos-kbidx-$$ENV" && \
	RG="rg-kbidx-$$ENV" && \
	SUB=$$(az account show --query id -o tsv) && \
	SCOPE="/subscriptions/$$SUB/resourceGroups/$$RG/providers/Microsoft.DocumentDB/databaseAccounts/$$COSMOS_ACCOUNT" && \
	echo "  Cosmos DB: $$COSMOS_ACCOUNT ($$RG)" && \
	echo "  Assigning Cosmos DB Built-in Data Contributor (native RBAC)..." && \
	az cosmosdb sql role assignment create \
		--account-name "$$COSMOS_ACCOUNT" \
		--resource-group "$$RG" \
		--role-definition-id "00000000-0000-0000-0000-000000000002" \
		--principal-id "$$USER_OID" \
		--scope "$$SCOPE" \
		-o none 2>/dev/null && \
	echo "  ✓ Cosmos DB data-plane role assigned." || \
	echo "  ✓ Cosmos DB data-plane role already assigned (or assignment skipped)."
	@echo ""
	@echo "  ARM-level roles are managed via Bicep (infra/)."
	@echo "  If missing, run: make azure-provision"

# ------------------------------------------------------------------------------
# Azure — Provision & Deploy
# ------------------------------------------------------------------------------
.PHONY: azure-provision azure-deploy

azure-provision: ## Provision all Azure resources (azd provision)
	azd provision

azure-deploy: ## Deploy functions, search index, and CU analyzer (azd deploy)
	azd deploy
	@echo "Configuring CU defaults and deploying kb-image-analyzer..."
	@(cd src/functions && uv run python -m manage_analyzers deploy)

# ------------------------------------------------------------------------------
# Azure — Run Pipeline
# ------------------------------------------------------------------------------
.PHONY: azure-upload-staging azure-convert azure-index

azure-upload-staging: ## Upload local kb/staging articles to Azure staging blob
	@echo "Uploading kb/staging/ to Azure staging blob container..."
	@ACCOUNT=$$(azd env get-value STAGING_STORAGE_ACCOUNT) && \
	for dir in kb/staging/*/; do \
		ARTICLE=$$(basename "$$dir") && \
		echo "  ↑ $$ARTICLE" && \
		az storage blob upload-batch \
			--destination staging \
			--source "$$dir" \
			--destination-path "$$ARTICLE" \
			--account-name "$$ACCOUNT" \
			--auth-mode login \
			--overwrite \
			--only-show-errors; \
	done
	@echo "Done."

azure-convert: ## Trigger fn-convert in Azure (analyzer=content-understanding|mistral-doc-ai)
ifndef analyzer
	@echo "Error: analyzer is required. Usage:" >&2
	@echo "  make azure-convert analyzer=content-understanding" >&2
	@echo "  make azure-convert analyzer=mistral-doc-ai" >&2
	@exit 1
endif
	@echo "Triggering fn-convert Azure Function (analyzer=$(analyzer))..."
	@FUNC_URL=$$(azd env get-value FUNCTION_APP_URL) && \
	ROUTE=$$(if [ "$(analyzer)" = "content-understanding" ]; then echo "convert"; else echo "convert-mistral"; fi) && \
	ENDPOINT="$$FUNC_URL/api/$$ROUTE" && \
	echo "  POST $$ENDPOINT" && \
	curl -sf --max-time 600 -X POST "$$ENDPOINT" -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
	@echo ""

azure-index: ## Trigger fn-index in Azure (processes serving → AI Search)
	@echo "Triggering fn-index Azure Function..."
	@FUNC_URL=$$(azd env get-value FUNCTION_APP_URL) && \
	ENDPOINT="$$FUNC_URL/api/index" && \
	echo "  POST $$ENDPOINT" && \
	curl -sf --max-time 600 -X POST "$$ENDPOINT" -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
	@echo ""

azure-index-summarize: ## Show AI Search index contents summary
	@cd src/functions && uv run python ../../scripts/functions/display-index-summary.py

# ------------------------------------------------------------------------------
# Azure — Web App
# ------------------------------------------------------------------------------
.PHONY: azure-deploy-app azure-app-url azure-app-logs

azure-deploy-app: ## Build & deploy the web app to Azure Container Apps
	azd deploy --service web-app

azure-app-url: ## Print the deployed web app URL
	@azd env get-value WEBAPP_URL

azure-app-logs: ## Stream live logs from the deployed web app
	@APP=$$(azd env get-value WEBAPP_NAME) && \
	RG=$$(azd env get-value RESOURCE_GROUP) && \
	az containerapp logs show --name $$APP --resource-group $$RG --type console --follow

# ------------------------------------------------------------------------------
# Azure — Agent (Foundry Hosted Agent)
# ------------------------------------------------------------------------------
.PHONY: azure-agent-deploy azure-agent-publish azure-agent azure-agent-logs azure-test-agent-dev azure-test-agent azure-test-app azure-test

azure-agent-deploy: ## Deploy the KB Agent to Foundry (dev mode)
	AZD_EXT_TIMEOUT=180 azd deploy --service agent

azure-agent-publish: ## Publish the agent (dedicated identity + stable endpoint)
	@bash scripts/publish-agent.sh

azure-agent: azure-agent-deploy azure-agent-publish ## Deploy + publish agent in one step

azure-test-agent-dev: ## Run agent integration tests against dev (unpublished) endpoint
	@cd src/agent && AGENT_ENDPOINT=$$(azd env get-value AGENT_AGENT_ENDPOINT) uv run pytest tests/ -v -m integration || test $$? -eq 5

azure-test-agent: ## Run agent integration tests against published Foundry endpoint
	@cd src/agent && AGENT_ENDPOINT=$$(azd env get-value AGENT_ENDPOINT) uv run pytest tests/ -v -m integration || test $$? -eq 5

azure-test-app: ## Run web app integration tests (Cosmos DB + Blob Storage)
	@cd src/web-app && uv run pytest tests/ -v -m integration || test $$? -eq 5

azure-test: azure-test-agent azure-test-app ## Run all Azure integration tests

azure-agent-logs: ## Stream agent logs from Foundry
	@AI_NAME=$$(azd env get-value AI_SERVICES_NAME) && \
	RG=$$(azd env get-value RESOURCE_GROUP) && \
	echo "Agent logs — use the Foundry portal for full tracing:" && \
	echo "  https://ai.azure.com" && \
	echo "" && \
	echo "Or query via CLI:" && \
	az monitor app-insights events show \
		--app $$(azd env get-value APPINSIGHTS_NAME) \
		--resource-group $$RG \
		--type traces \
		--order-by timestamp \
		--top 50

# ------------------------------------------------------------------------------
# Azure — Cleanup
# ------------------------------------------------------------------------------
.PHONY: azure-clean-storage azure-clean-index azure-clean

azure-clean-storage: ## Empty staging and serving blob containers in Azure
	@echo "Cleaning staging container..."
	az storage blob delete-batch \
		--account-name $$(azd env get-value STAGING_STORAGE_ACCOUNT) \
		--source staging \
		--auth-mode login
	@echo "Cleaning serving container..."
	az storage blob delete-batch \
		--account-name $$(azd env get-value SERVING_STORAGE_ACCOUNT) \
		--source serving \
		--auth-mode login
	@echo "Done."

azure-clean-index: ## Delete the AI Search index
	@echo "Deleting kb-articles index..."
	@cd src/functions && uv run python -c "\
	from shared.config import config; \
	from azure.search.documents.indexes import SearchIndexClient; \
	from azure.identity import DefaultAzureCredential; \
	c = SearchIndexClient(config.search_endpoint, DefaultAzureCredential()); \
	c.delete_index('kb-articles'); \
	print('  Index deleted.')" 2>/dev/null || echo "  Index did not exist."

azure-clean: azure-clean-storage azure-clean-index ## Clean all Azure data (storage + index + analyzer)
	@echo "Deleting kb-image-analyzer..."
	@(cd src/functions && uv run python -m manage_analyzers delete) 2>/dev/null || true
	@echo "All Azure data cleaned."
