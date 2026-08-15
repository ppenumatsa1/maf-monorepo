SHELL := /bin/bash
COMPOSE_ENV_FILE ?= backend/.env
PROJECT_ROOT := $(CURDIR)
PRIVATE_DEPLOYMENT_PROFILE := ../deployment/profiles/foundry-private.env
SHARED_PROFILE_APPLICATOR := ../deployment/apply-azd-profile.sh

.PHONY: help bootstrap venv-backend install-backend install-frontend ensure-backend-env ensure-foundry-deploy-env ensure-test-postgres \
	run-backend run-frontend format lint test test-backend eval-backend eval-foundry eval-all test-e2e test-e2e-selected-thread manual-matrix \
	parity-all run-mock-mcp up down logs ps docker-test \
	validate-quick validate-full clean \
	foundry-up foundry-preflight foundry-iac-validate foundry-release-preflight foundry-package \
	foundry-profile test-foundry-portability \
	foundry-provision-preview foundry-provision foundry-project-connections foundry-deploy \
	foundry-app-deploy foundry-app-images-verify foundry-app-only-preflight foundry-hosted-app-deploy \
	foundry-postgres-bootstrap foundry-postgres-readiness foundry-app-only-release \
	foundry-evidence foundry-release foundry-smoke foundry-access-path release-history-migration-plan

help:
	@echo "Available targets:"
	@echo "  up              - Start all servers with Docker (backend, frontend, mock-mcp)"
	@echo "  down            - Stop all Docker servers"
	@echo "  logs            - Tail Docker logs"
	@echo "  ps              - Show running Docker services"
	@echo "  bootstrap       - Create backend venv + install backend/frontend/playwright deps"
	@echo "  run-backend     - Start FastAPI backend locally on :8000"
	@echo "  run-frontend    - Start Vite frontend locally on :5173"
	@echo "  format          - Format Python files (ruff format)"
	@echo "  lint            - Lint Python files (ruff check)"
	@echo "  test            - Run lint + backend tests"
	@echo "  test-backend    - Run backend pytest suite"
	@echo "  eval-backend    - Run deterministic workflow contract eval harness"
	@echo "  eval-foundry    - Run report-only Foundry evaluator run"
	@echo "  eval-all        - Run deterministic and Foundry evals"
	@echo "  test-e2e        - Run workflow and selected-thread Playwright tests locally"
	@echo "  test-e2e-selected-thread - Run focused selected-thread integration tests"
	@echo "  manual-matrix   - Run ORD-1001..ORD-1010 manual verification matrix"
	@echo "  parity-all      - Run fast parity gate across local + Azure + Foundry"
	@echo "  run-mock-mcp    - Start local authenticated MCP simulator"
	@echo "  docker-test     - Run Playwright tests in Docker compose profile"
	@echo "  validate-quick  - Fast redeploy validation (Playwright + smoke if API_URL set)"
	@echo "  validate-full   - Full validation (test + eval + e2e + design-review)"
	@echo "  foundry-up      - Self-contained Foundry hosted-agent azd up (BYO VNET + private deps)"
	@echo "  foundry-profile - Validate and apply the canonical secret-free private target profile"
	@echo "  test-foundry-portability - Validate private release/profile portability contracts"
	@echo "  foundry-preflight - Verify private release inputs without changing Azure"
	@echo "  foundry-iac-validate - Compile private IaC without writing a generated template"
	@echo "  foundry-release-preflight - Run independent read-only release checks concurrently"
	@echo "  foundry-package - Freshly sync hosted source and validate AZD packaging"
	@echo "  foundry-provision-preview - Preview private infrastructure changes without applying them"
	@echo "  foundry-provision - Provision private core infrastructure without Foundry secret connections"
	@echo "  foundry-project-connections - Provision Foundry connections after project identity propagation"
	@echo "  foundry-deploy  - Deploy hosted agent to Foundry (after provision/up)"
	@echo "  foundry-app-deploy - Deploy private backend and public frontend Container Apps"
	@echo "  foundry-app-only-preflight - Read-only validation of existing private app-release dependencies"
	@echo "  foundry-app-images-verify - Verify active Container App revisions use the selected private ACR"
	@echo "  foundry-hosted-app-deploy - Build, push, and activate a hosted-agent version without provisioning"
	@echo "  foundry-postgres-bootstrap - Apply schema and least-privilege runtime credentials from the private runner"
	@echo "  foundry-postgres-readiness - Verify private-only PostgreSQL networking and runtime privileges"
	@echo "  foundry-app-only-release - Deploy only ACA revisions and a hosted-agent image/version"
	@echo "  foundry-evidence - Collect hosted E2E, evaluation, and telemetry evidence"
	@echo "  foundry-release - Test, provision private PostgreSQL, deploy, and collect evidence"
	@echo "  foundry-smoke   - Invoke hosted agent health check via responses protocol"
	@echo "  foundry-access-path - Recreate the private runner VM/Bastion through the selected AZD environment"
	@echo "  clean           - Remove caches and test artifacts"

bootstrap: install-backend install-frontend

venv-backend:
	cd backend && python3 -m venv .venv

install-backend:
	FORCE_BACKEND_VENV_REFRESH=true ./scripts/foundry/ensure_backend_venv.sh

install-frontend:
	cd frontend && npm install
	cd scripts/playwright && npm install

ensure-backend-env:
	./scripts/foundry/ensure_backend_venv.sh

ensure-foundry-deploy-env: ensure-backend-env
	. backend/.venv/bin/activate && python -c "import azure.ai.projects"

ensure-test-postgres:
	@DATABASE_URL="$${DATABASE_URL:-$${FOUNDRY_RUNTIME_DATABASE_URL:-$${RUNTIME_DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/maf_workflow?sslmode=disable}}}" \
		./scripts/local/ensure_test_postgres.sh

run-backend: ensure-backend-env
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

run-frontend:
	cd frontend && npm run dev

format: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff format .

lint: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff check .

test: lint test-backend

test-backend: ensure-backend-env ensure-test-postgres
	cd backend && . .venv/bin/activate && pytest -q

eval-backend: ensure-backend-env ensure-test-postgres
	cd backend && . .venv/bin/activate && python -m evals.eval_runner

eval-foundry: ensure-backend-env
	cd backend && . .venv/bin/activate && \
		foundry_env_name="$$(bash -c 'source ../../deployment/profile.sh; deployment_profile_load "$$1"; deployment_profile_validate; deployment_profile_export; printf "%s" "$$AZURE_ENV_NAME"' _ "../$(PRIVATE_DEPLOYMENT_PROFILE)")"; \
		foundry_env_file="../infra/foundry-hosted/.azure/$${foundry_env_name}/.env"; \
		if [[ -f "$$foundry_env_file" ]]; then \
			set -a; . "$$foundry_env_file"; set +a; \
		fi; \
		if [[ -z "$${FOUNDRY_PROJECTS_ENDPOINT:-}" && -n "$${FOUNDRY_PROJECT_ENDPOINT:-}" ]]; then \
			export FOUNDRY_PROJECTS_ENDPOINT="$$FOUNDRY_PROJECT_ENDPOINT"; \
		fi; \
		if [[ -z "$${FOUNDRY_MODEL_DEPLOYMENT_NAME:-}" && -n "$${AZURE_AI_MODEL_DEPLOYMENT_NAME:-}" ]]; then \
			export FOUNDRY_MODEL_DEPLOYMENT_NAME="$$AZURE_AI_MODEL_DEPLOYMENT_NAME"; \
		fi; \
		python -m evals.foundry_eval_runner

eval-all: eval-backend eval-foundry

test-e2e-selected-thread:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd frontend && PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts; \
	else \
		cd frontend && npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts; \
	fi

test-e2e:
	@set -euo pipefail; \
	if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd scripts/playwright && npm run test:e2e; \
		PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" $(MAKE) -C "$(PROJECT_ROOT)" test-e2e-selected-thread; \
	else \
		$(MAKE) ensure-backend-env ensure-test-postgres; \
		backend_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
		backend_url="http://127.0.0.1:$${backend_port}"; \
		backend_log="/tmp/maf-backend-e2e-$${backend_port}.log"; \
		( \
			cd backend && . .venv/bin/activate && \
			APP_ENV=local \
			WORKFLOW_MODE=maf_sdk \
			STORE_PROVIDER=postgres \
			RAG_PROVIDER=pgvector \
			MEMORY_PROVIDER=postgres \
			MCP_SERVER_URL= \
			uvicorn app.main:app --host 127.0.0.1 --port "$${backend_port}" \
		) > "$${backend_log}" 2>&1 & \
		backend_pid="$$!"; \
		disown "$${backend_pid}" 2>/dev/null || true; \
		frontend_pid=""; \
		frontend_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
		frontend_url="http://127.0.0.1:$${frontend_port}"; \
		frontend_log="/tmp/maf-frontend-e2e-$${frontend_port}.log"; \
		trap 'kill "${backend_pid:-}" 2>/dev/null || true; kill "${frontend_pid:-}" 2>/dev/null || true' EXIT; \
		for _ in {1..45}; do \
			health_json="$$(curl -fsS "$${backend_url}/api/health" 2>/dev/null || true)"; \
			if [[ "$${health_json}" == *'"workflow_mode":"maf_sdk"'* ]]; then \
				break; \
			fi; \
			sleep 1; \
		done; \
		health_json="$$(curl -fsS "$${backend_url}/api/health" 2>/dev/null || true)"; \
		if [[ "$${health_json}" != *'"workflow_mode":"maf_sdk"'* ]]; then \
			echo "Backend failed to become ready for E2E. See $${backend_log}"; \
			exit 1; \
		fi; \
		(cd frontend && VITE_PROXY_TARGET="$${backend_url}" node_modules/.bin/vite --host 127.0.0.1 --port "$${frontend_port}" --strictPort) > "$${frontend_log}" 2>&1 & \
		frontend_pid="$$!"; \
		disown "$${frontend_pid}" 2>/dev/null || true; \
		for _ in {1..30}; do \
			curl -fsS "$${frontend_url}" >/dev/null && break; \
			sleep 1; \
		done; \
		proxy_health="$$(curl -fsS "$${frontend_url}/api/health" 2>/dev/null || true)"; \
		if [[ "$${proxy_health}" != *'"workflow_mode":"maf_sdk"'* || "$${proxy_health}" != *'"environment":"local"'* ]]; then \
			echo "Frontend proxy is not targeting the isolated local backend. See $${frontend_log}"; \
			exit 1; \
		fi; \
		cd scripts/playwright && PLAYWRIGHT_BASE_URL="$${frontend_url}" npm run test:e2e; \
		PLAYWRIGHT_BASE_URL="$${frontend_url}" $(MAKE) -C "$(PROJECT_ROOT)" test-e2e-selected-thread; \
		e2e_status="$$?"; \
		kill "$${backend_pid}" "$${frontend_pid}" 2>/dev/null || true; \
		wait "$${backend_pid}" 2>/dev/null || true; \
		wait "$${frontend_pid}" 2>/dev/null || true; \
		exit "$${e2e_status}"; \
	fi

manual-matrix:
	scripts/manual/run-manual-matrix.sh "$${API_URL:-http://localhost:8000}" $${MANUAL_MATRIX_ARGS:-}

parity-all:
	scripts/parity/run-parity-matrix.sh --targets local foundry --profile fast

run-mock-mcp: ensure-backend-env
	. backend/.venv/bin/activate && uvicorn scripts.mcp.mock_mcp_server:app --reload --port 8011

up:
	@set -euo pipefail; \
	workflow_mode="$$(grep -E '^[[:space:]]*WORKFLOW_MODE=' $(COMPOSE_ENV_FILE) | tail -1 | cut -d= -f2- | tr -d '"' || true)"; \
	hosted_key="$$(grep -E '^[[:space:]]*FOUNDRY_HOSTED_API_KEY=' $(COMPOSE_ENV_FILE) | tail -1 | cut -d= -f2- | tr -d '"' || true)"; \
	if [[ "$$workflow_mode" == "foundry_hosted" && -z "$$hosted_key" ]]; then \
		if command -v az >/dev/null 2>&1; then \
			token="$$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv 2>/dev/null || true)"; \
			if [[ -n "$$token" ]]; then \
				echo "Using host Azure CLI token for Foundry hosted responses."; \
				FOUNDRY_HOSTED_API_KEY="Bearer $$token" docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp; \
			else \
				echo "WARN: Could not acquire Azure CLI token. Set FOUNDRY_HOSTED_API_KEY in $(COMPOSE_ENV_FILE)."; \
				docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp; \
			fi; \
		else \
			echo "WARN: Azure CLI not found on host. Set FOUNDRY_HOSTED_API_KEY in $(COMPOSE_ENV_FILE)."; \
			docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp; \
		fi; \
	else \
		docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp; \
	fi
	@echo "Frontend: http://localhost:5173"
	@echo "Backend health: http://localhost:8000/health"

down:
	docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans

logs:
	docker compose --env-file $(COMPOSE_ENV_FILE) logs -f --tail=200

ps:
	docker compose --env-file $(COMPOSE_ENV_FILE) ps

docker-test:
	@set -euo pipefail; \
	project="maf-order-resolution-agent-test"; \
	backend_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
	frontend_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
	postgres_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
	mcp_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
	trap 'docker compose -p "$$project" --env-file $(COMPOSE_ENV_FILE) --profile test down --volumes --remove-orphans >/dev/null 2>&1 || true' EXIT; \
	BACKEND_PORT="$$backend_port" FRONTEND_PORT="$$frontend_port" POSTGRES_PORT="$$postgres_port" MCP_PORT="$$mcp_port" \
		docker compose -p "$$project" --env-file $(COMPOSE_ENV_FILE) --profile test up --build --abort-on-container-exit playwright

validate-quick:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		$(MAKE) test-e2e; \
	elif [[ -n "$${WEB_URL:-}" ]]; then \
		PLAYWRIGHT_BASE_URL="$${WEB_URL}" $(MAKE) test-e2e; \
	else \
		$(MAKE) test-e2e; \
	fi
	@true

validate-full:
	$(MAKE) test
	$(MAKE) eval-backend
	$(MAKE) test-e2e
	./scripts/skills/design-review-skill.sh

foundry-up:
	$(MAKE) foundry-provision
	$(MAKE) foundry-project-connections
	$(MAKE) foundry-deploy

foundry-profile:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill AZD_PROJECT_DIR="$(CURDIR)/infra/foundry-hosted" \
		bash "$(SHARED_PROFILE_APPLICATOR)" "$(PRIVATE_DEPLOYMENT_PROFILE)"

test-foundry-portability:
	bash ./scripts/foundry/tests/test_release_portability_contract.sh

foundry-preflight: foundry-profile
	./scripts/foundry/preflight_private_release.sh

foundry-iac-validate:
	az bicep build --file infra/foundry-hosted/iac/main.bicep --stdout >/dev/null

foundry-release-preflight:
	@$(MAKE) -j2 foundry-preflight foundry-iac-validate

foundry-package:
	./scripts/foundry/sync_hosted_source.sh
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd package --no-prompt

foundry-provision-preview: foundry-profile
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --preview --no-prompt $(if $(FOUNDRY_PROVISION_NO_STATE),--no-state,)

foundry-provision: foundry-profile
	bash ./scripts/foundry/provision_private_infrastructure.sh

foundry-project-connections:
	$(MAKE) foundry-preflight
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/ensure_foundry_azd_defaults.sh
	cd infra/foundry-hosted && \
		AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set MANAGE_PROJECT_CONNECTIONS true && \
		AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt $(if $(FOUNDRY_PROVISION_NO_STATE),--no-state,) && \
		FOUNDRY_POST_PROVISION_HYDRATE=1 AZURE_DEV_USER_AGENT=microsoft_foundry_skill ../../scripts/foundry/ensure_foundry_azd_defaults.sh

foundry-deploy: ensure-foundry-deploy-env
	@test -f backend/Dockerfile.hosted
	@test -f backend/foundry/main.py
	@AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/ensure_foundry_azd_defaults.sh
	@$(MAKE) foundry-package
	@./scripts/foundry/deploy_hosted_container.sh

foundry-app-deploy:
	@test -f backend/Dockerfile
	@test -f frontend/Dockerfile
	@set -euo pipefail; \
	cd infra/foundry-hosted; \
	resource_group="$$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AZURE_RESOURCE_GROUP)"; \
	backend_name="$$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value BACKEND_CONTAINER_APP_NAME)"; \
	runtime_database_url="$$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value RUNTIME_DATABASE_URL)"; \
	az containerapp secret set --resource-group "$$resource_group" --name "$$backend_name" \
		--secrets "database-url=$$runtime_database_url" --only-show-errors --output none; \
	az containerapp update --resource-group "$$resource_group" --name "$$backend_name" \
		--set-env-vars DATABASE_URL=secretref:database-url DB_SCHEMA_MANAGED_EXTERNALLY=true \
		--only-show-errors --output none
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy backend --no-prompt
	@set -euo pipefail; \
	cd infra/foundry-hosted; \
	resource_group="$$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AZURE_RESOURCE_GROUP)"; \
	backend_name="$$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value BACKEND_CONTAINER_APP_NAME)"; \
	az containerapp update --resource-group "$$resource_group" --name "$$backend_name" \
		--set-env-vars DATABASE_URL=secretref:database-url DB_SCHEMA_MANAGED_EXTERNALLY=true \
		--only-show-errors --output none
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy frontend --no-prompt

foundry-app-images-verify:
	./scripts/foundry/verify_private_app_images.sh

foundry-app-only-preflight:
	./scripts/foundry/validate_private_app_release.sh

foundry-postgres-bootstrap:
	POSTGRES_PROFILE_FILE="$(PRIVATE_DEPLOYMENT_PROFILE)" \
	POSTGRES_AZD_ENVIRONMENT="$${AZD_ENVIRONMENT_NAME:-$${AZURE_ENV_NAME:-ora-foundry-private}}" \
	./scripts/foundry/provision_postgres_runtime_credentials.sh

foundry-postgres-readiness:
	./scripts/foundry/verify_private_postgres_readiness.sh

foundry-hosted-app-deploy: ensure-foundry-deploy-env
	@test -f backend/Dockerfile.hosted
	@test -f backend/foundry/main.py
	@./scripts/foundry/sync_hosted_source.sh
	@./scripts/foundry/deploy_hosted_container.sh

foundry-app-only-release:
	$(MAKE) foundry-app-only-preflight
	$(MAKE) foundry-postgres-readiness
	PRIVATE_RELEASE_PREREQUISITES_PASSED=true ./scripts/foundry/deploy_private_app_release.sh

foundry-evidence: ensure-backend-env
	./scripts/foundry/collect_private_release_evidence.sh

release-history-migration-plan:
	python3 ./scripts/foundry/migrate_release_history.py --project-root "$(CURDIR)"

foundry-release:
	$(MAKE) test
	$(MAKE) foundry-release-preflight
	$(MAKE) foundry-provision-preview
	$(MAKE) foundry-provision
	$(MAKE) foundry-postgres-bootstrap
	$(MAKE) foundry-postgres-readiness
	$(MAKE) foundry-project-connections
	$(MAKE) foundry-app-only-release
	$(MAKE) foundry-evidence

foundry-smoke:
	@set -euo pipefail; \
	message="$${SMOKE_MESSAGE:-Resolve delayed order ORD-1009}"; \
	attempt=1; \
	max_attempts="$${SMOKE_MAX_ATTEMPTS:-6}"; \
	while [[ "$$attempt" -le "$$max_attempts" ]]; do \
		set +e; \
		if [[ -n "$${SMOKE_THREAD_ID:-}" ]]; then \
			output="$$(cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke order-resolution-hosted "$$message" --protocol responses --conversation-id "$${SMOKE_THREAD_ID}" --no-prompt 2>&1)"; \
		else \
			output="$$(cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke order-resolution-hosted "$$message" --protocol responses --new-conversation --new-session --no-prompt 2>&1)"; \
		fi; \
		rc="$$?"; \
		set -e; \
		if [[ "$$rc" -eq 0 ]]; then \
			echo "$$output"; \
			exit 0; \
		fi; \
		if echo "$$output" | grep -Eqi 'context deadline exceeded|session_not_ready|HTTP (404|409|429|5[0-9]{2})'; then \
			echo "Transient smoke invoke failure ($$attempt/$$max_attempts); retrying in 15s..."; \
			echo "$$output"; \
			attempt="$$((attempt + 1))"; \
			sleep 15; \
			continue; \
		fi; \
		echo "$$output"; \
		exit "$$rc"; \
	done; \
	echo "Smoke invoke failed after $$max_attempts attempts."; \
	exit 1

foundry-access-path:
	@set -euo pipefail; \
	key_path="$${RUNNER_SSH_PUBKEY_PATH:-}"; \
	[[ -n "$$key_path" ]] || { \
		echo "RUNNER_SSH_PUBKEY_PATH is required and must point to the runner VM SSH public key."; \
		exit 1; \
	}; \
	[[ -f "$$key_path" ]] || { \
		echo "RUNNER_SSH_PUBKEY_PATH does not exist: $$key_path"; \
		exit 1; \
	}; \
	runner_ssh_public_key="$$(tr -d '\r\n' < "$$key_path")"; \
	[[ -n "$$runner_ssh_public_key" ]] || { \
		echo "RUNNER_SSH_PUBKEY_PATH is empty: $$key_path"; \
		exit 1; \
	}; \
	profile_env="$$(bash -c 'source ../deployment/profile.sh; deployment_profile_load "$$1"; deployment_profile_validate; deployment_profile_export; printf "%s" "$$AZURE_ENV_NAME"' _ "$(PRIVATE_DEPLOYMENT_PROFILE)")"; \
	[[ -n "$$profile_env" ]] || { echo "Canonical private profile is missing AZURE_ENV_NAME."; exit 1; }; \
	cd infra/foundry-hosted; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$$profile_env" --no-prompt; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ../../scripts/foundry/ensure_foundry_azd_defaults.sh; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill $(MAKE) -C ../.. foundry-preflight; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set CREATE_PRIVATE_RUNNER_ACCESS true; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set CREATE_RUNNER_VM true; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set MANAGE_PROJECT_CONNECTIONS false; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set RUNNER_VM_SSH_PUBLIC_KEY "$$runner_ssh_public_key"; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache scripts/playwright/test-results scripts/playwright/playwright-report
