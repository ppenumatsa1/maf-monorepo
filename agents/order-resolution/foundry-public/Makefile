SHELL := /bin/bash
COMPOSE_ENV_FILE ?= $(if $(wildcard backend/.env),backend/.env,backend/.env.example)
FOUNDRY_DEPLOYMENT_PROFILE ?= deployment/profiles/foundry-public.env

.PHONY: help bootstrap venv-backend install-backend install-frontend ensure-backend-env ensure-test-postgres \
	run-backend run-frontend format lint test test-backend eval-backend eval-foundry eval-foundry-config eval-all test-e2e manual-matrix \
	test-e2e-selected-thread \
	run-mock-mcp up down logs ps docker-test \
	validate-quick validate-full test-scripts test-deployment-profile test-foundry-portability clean \
	test-capacity-preflight test-preview-safety test-release-evidence \
	foundry-profile-apply foundry-bootstrap foundry-bootstrap-env foundry-iac-build foundry-python-wheelhouse foundry-package foundry-up foundry-provision foundry-provision-ready \
	foundry-provision-preview foundry-reuse-preview foundry-release-preflight \
	foundry-postgres-schema foundry-postgres-credentials \
	foundry-postgres-readiness foundry-backend-deploy foundry-backend-deploy-ready \
	foundry-frontend-deploy foundry-frontend-deploy-ready foundry-app-deploy \
	foundry-deploy foundry-deploy-ready foundry-release-deploy foundry-smoke \
	foundry-model-preflight foundry-capacity-preflight-full foundry-runtime-connection foundry-runtime-connection-ready foundry-runtime-connection-check \
	foundry-hosted-rbac foundry-hosted-e2e \
	foundry-eval foundry-appinsights-connection foundry-telemetry \
	foundry-verify foundry-evidence foundry-release foundry-release-migration-plan \
	foundry-evaluator-rbac-check \
	foundry-activity-plan foundry-activity-apply foundry-activity-rollback test-foundry-activity-endpoint \
	foundry-teams-plan foundry-teams-preview foundry-teams-deploy-bot foundry-teams-package foundry-teams-publish \
	foundry-teams-verify-local-state foundry-teams-rollback-plan test-foundry-teams-publishing

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
	@echo "  eval-foundry    - Run report-only Foundry evaluator using nested azd configuration"
	@echo "  eval-foundry-config - Verify the selected nested azd evaluator configuration"
	@echo "  eval-all        - Run deterministic and Foundry evals"
	@echo "  test-e2e        - Run workflow and selected-thread Playwright tests"
	@echo "  test-e2e-selected-thread - Run the focused selected-thread integration test"
	@echo "  manual-matrix   - Run ORD-1001..ORD-1010 manual verification matrix"
	@echo "  run-mock-mcp    - Start local authenticated MCP simulator"
	@echo "  docker-test     - Run Playwright tests in Docker compose profile"
	@echo "  validate-quick  - Fast redeploy validation (Playwright + smoke if API_URL set)"
	@echo "  validate-full   - Full validation (test + eval + e2e + design-review)"
	@echo "  test-scripts     - Run portable bootstrap and PostgreSQL helper contracts"
	@echo "  test-deployment-profile - Validate secret-free target profiles"
	@echo "  foundry-profile-apply FOUNDRY_DEPLOYMENT_PROFILE=/secure/path/profile.env"
	@echo "                   - Select a secret-free bootstrap or reuse target"
	@echo "  foundry-bootstrap - Hydrate local AZD outputs for an existing target"
	@echo "  foundry-bootstrap-env - Populate deterministic bootstrap parameters"
	@echo "  foundry-iac-build - Compile the public Foundry Bicep template"
	@echo "  foundry-python-wheelhouse - Download hash-verified Python 3.13 Linux AMD64 runtime wheels"
	@echo "  foundry-package - Freshly sync hosted source and validate AZD packaging"
	@echo "  foundry-provision - Apply bootstrap creation or non-mutating reuse"
	@echo "  foundry-provision-preview - Preview a full-infrastructure plan without apply"
	@echo "  foundry-reuse-preview - Require a zero-mutation routine reuse preview"
	@echo "  foundry-release-preflight - Run read-only capacity, preview, DB, and connection gates"
	@echo "  foundry-postgres-schema - Apply the canonical PostgreSQL schema"
	@echo "  foundry-postgres-credentials - Provision/rotate the runtime credential"
	@echo "  foundry-app-deploy - Verify readiness once, then deploy backend and frontend concurrently"
	@echo "  foundry-deploy  - Verify readiness, package, and deploy the hosted agent"
	@echo "  foundry-release-deploy - Package, activate hosted first, then deploy backend/frontend concurrently"
	@echo "  foundry-model-preflight - Read-only exact-resource and zero-growth app-only capacity gate"
	@echo "  foundry-capacity-preflight-full - Read-only incremental quota gate for reviewed infrastructure apply"
	@echo "  foundry-runtime-connection - Full-authority PostgreSQL readiness and project connection convergence"
	@echo "  foundry-runtime-connection-check - Verify the existing project CustomKeys connection without mutation"
	@echo "  foundry-hosted-rbac - Converge the hosted identity's account-scoped OpenAI User role"
	@echo "  foundry-smoke   - Invoke hosted agent health check and write secret-free evidence"
	@echo "  foundry-hosted-e2e - Run fresh low/high-risk and damaged-item HITL approval/resume checks"
	@echo "  foundry-eval    - Run the report-only Foundry trace-evaluation gate"
	@echo "  foundry-telemetry - Verify Application Insights after hosted E2E evidence exists"
	@echo "  foundry-verify  - Verify exact active images, topology, proxy health, hosted version, RBAC, and DB parity"
	@echo "  foundry-evidence - Aggregate the current release window into one secret-free JSON report"
	@echo "  foundry-release - Run the authenticated, gated public release DAG"
	@echo "  foundry-activity-plan - Preview merge-preserving Activity endpoint reconciliation"
	@echo "  foundry-activity-apply - Retain Responses/Entra and add Activity/BotServiceRbac"
	@echo "  foundry-activity-rollback - Remove Activity and Bot authorization only"
	@echo "  test-foundry-activity-endpoint - Run credential-free endpoint reconciler tests"
	@echo "  foundry-teams-plan - Validate the versioned Shared publication plan"
	@echo "  foundry-teams-preview - Run ARM what-if for Bot Service and MsTeamsChannel"
	@echo "  foundry-teams-deploy-bot - Deploy Bot Service and MsTeamsChannel with Bicep"
	@echo "  foundry-teams-package - Generate the reviewed Microsoft 365 app package"
	@echo "  foundry-teams-publish - Publish the explicit Shared app version"
	@echo "  foundry-teams-verify-local-state - Verify sanitized local publication evidence"
	@echo "  foundry-teams-rollback-plan - Show non-destructive rollback boundaries"
	@echo "  test-foundry-teams-publishing - Run publication and Teams IaC contracts"
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

test-scripts:
	PYTHONPATH=backend:. backend/.venv/bin/pytest -q \
		scripts/foundry/tests/test_postgres_runtime_credentials.py \
		scripts/foundry/tests/test_hosted_deployment_contract.py \
		scripts/foundry/tests/test_release_evidence.py \
		scripts/foundry/tests/test_capacity_preflight.py \
		scripts/foundry/tests/test_preview_safety.py
	bash scripts/foundry/tests/test_bootstrap_infrastructure_contract.sh
	bash scripts/foundry/tests/test_release_scripts_contract.sh
	bash scripts/foundry/tests/test_release_portability_contract.sh
	$(MAKE) test-foundry-activity-endpoint
	$(MAKE) test-foundry-teams-publishing

test-foundry-activity-endpoint:
	python3 -m unittest discover -s scripts/foundry/tests -p 'test_activity_endpoint_reconciler.py'

test-foundry-teams-publishing:
	python3 -m unittest discover -s scripts/foundry/tests -p 'test_teams_publishing.py'
	python3 -m unittest discover -s infra/foundry-hosted/iac/teams/tests -p 'test_teams_iac_contract.py'

test-foundry-portability:
	bash scripts/foundry/tests/test_release_portability_contract.sh

test-capacity-preflight:
	PYTHONPATH=backend:. backend/.venv/bin/pytest -q scripts/foundry/tests/test_capacity_preflight.py

test-preview-safety:
	PYTHONPATH=backend:. backend/.venv/bin/pytest -q scripts/foundry/tests/test_preview_safety.py

test-release-evidence:
	PYTHONPATH=backend:. backend/.venv/bin/pytest -q scripts/foundry/tests/test_release_evidence.py

test-deployment-profile:
	bash deployment/tests/test-profile.sh

eval-backend: ensure-backend-env ensure-test-postgres
	cd backend && . .venv/bin/activate && python -m evals.eval_runner

eval-foundry: ensure-backend-env
	./scripts/foundry/run_foundry_eval.sh

foundry-eval: eval-foundry

eval-foundry-config:
	./scripts/foundry/run_foundry_eval.sh --check

eval-all: eval-backend eval-foundry

test-e2e-selected-thread:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd frontend && PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts; \
	else \
		cd frontend && npm run test:e2e -- tests/e2e/selected-thread-integrations.spec.ts; \
	fi

test-e2e: foundry-python-wheelhouse
	@set -euo pipefail; \
	if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd scripts/playwright && npm run test:e2e; \
		PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" $(MAKE) -C "$(CURDIR)" test-e2e-selected-thread; \
	else \
		set -euo pipefail; \
		free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'; }; \
		backend_port="$${E2E_BACKEND_HOST_PORT:-$$(free_port)}"; \
		postgres_port="$${E2E_POSTGRES_HOST_PORT:-$$(free_port)}"; \
		mock_mcp_port="$${E2E_MOCK_MCP_HOST_PORT:-$$(free_port)}"; \
		compose_project="$${E2E_COMPOSE_PROJECT_NAME:-maf-e2e-$${backend_port}}"; \
		echo "Starting isolated E2E stack '$${compose_project}' with backend on :$${backend_port}."; \
		cleanup() { \
			if [[ -n "$${frontend_pid:-}" ]]; then kill "$${frontend_pid}" 2>/dev/null || true; wait "$${frontend_pid}" 2>/dev/null || true; fi; \
			COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans >/dev/null 2>&1 || true; \
		}; \
		trap cleanup EXIT; \
		COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend; \
		backend_url="http://127.0.0.1:$${backend_port}"; \
		for _ in {1..60}; do \
			curl -fsS "$${backend_url}/health" >/dev/null && break; \
			sleep 1; \
		done; \
		curl -fsS "$${backend_url}/health" >/dev/null; \
		frontend_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
		frontend_url="http://127.0.0.1:$${frontend_port}"; \
		(cd frontend && VITE_PROXY_TARGET="$${backend_url}" node_modules/.bin/vite --host 127.0.0.1 --port "$${frontend_port}" --strictPort) >/dev/null 2>&1 & \
		frontend_pid="$$!"; \
		for _ in {1..30}; do \
			curl -fsS "$${frontend_url}" >/dev/null && break; \
			sleep 1; \
		done; \
		PLAYWRIGHT_BASE_URL="$${frontend_url}" bash -c 'cd scripts/playwright && npm run test:e2e'; \
		PLAYWRIGHT_BASE_URL="$${frontend_url}" $(MAKE) -C "$(CURDIR)" test-e2e-selected-thread; \
	fi

manual-matrix:
	scripts/manual/run-manual-matrix.sh "$${API_URL:-http://localhost:8000}" $${MANUAL_MATRIX_ARGS:-}

run-mock-mcp: ensure-backend-env
	. backend/.venv/bin/activate && uvicorn scripts.mcp.mock_mcp_server:app --reload --port 8011

up: foundry-python-wheelhouse
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

docker-test: foundry-python-wheelhouse
	@set -euo pipefail; \
	free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'; }; \
	backend_port="$${E2E_BACKEND_HOST_PORT:-$$(free_port)}"; \
	frontend_port="$${E2E_FRONTEND_HOST_PORT:-$$(free_port)}"; \
	postgres_port="$${E2E_POSTGRES_HOST_PORT:-$$(free_port)}"; \
	mock_mcp_port="$${E2E_MOCK_MCP_HOST_PORT:-$$(free_port)}"; \
	compose_project="$${E2E_COMPOSE_PROJECT_NAME:-maf-e2e-docker-$${backend_port}}"; \
	cleanup() { \
		COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" FRONTEND_HOST_PORT="$${frontend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans >/dev/null 2>&1 || true; \
	}; \
	trap cleanup EXIT; \
	COMPOSE_PROJECT_NAME="$${compose_project}" BACKEND_HOST_PORT="$${backend_port}" FRONTEND_HOST_PORT="$${frontend_port}" POSTGRES_HOST_PORT="$${postgres_port}" MOCK_MCP_HOST_PORT="$${mock_mcp_port}" docker compose --env-file $(COMPOSE_ENV_FILE) --profile test up --build --abort-on-container-exit --exit-code-from playwright playwright

validate-quick:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		$(MAKE) test-e2e; \
	elif [[ -n "$${WEB_URL:-}" ]]; then \
		PLAYWRIGHT_BASE_URL="$${WEB_URL}" $(MAKE) test-e2e; \
	else \
		$(MAKE) test-e2e; \
	fi
validate-full:
	$(MAKE) test
	$(MAKE) eval-backend
	$(MAKE) test-e2e
	./scripts/skills/design-review-skill.sh

foundry-bootstrap:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/bootstrap_azd_env.sh

foundry-bootstrap-env:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/prepare_bootstrap_env.sh

foundry-profile-apply:
	@set -euo pipefail; \
	profile="$(FOUNDRY_DEPLOYMENT_PROFILE)"; \
	[[ -f "$$profile" && ! -L "$$profile" ]] || { \
		echo "External deployment profile is required: $$profile" >&2; \
		exit 1; \
	}; \
	AZD_PROJECT_DIR="$(CURDIR)/infra/foundry-hosted" \
		bash ./deployment/apply-azd-profile.sh "$$profile"

foundry-iac-build:
	az bicep build --file infra/foundry-hosted/iac/main.bicep
	az bicep build --file infra/foundry-hosted/iac/modules/foundry-project-runtime-secret-connection.bicep --stdout >/dev/null
	az bicep build --file infra/foundry-hosted/iac/teams/main.bicep --stdout >/dev/null

foundry-python-wheelhouse: ensure-backend-env
	./scripts/foundry/build_python_wheelhouse.sh

foundry-package: foundry-python-wheelhouse
	@set -euo pipefail; \
	timing_enabled=0; \
	if [[ -n "$${FOUNDRY_RELEASE_ID:-}" ]]; then \
		timing_enabled=1; \
		python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage package_build --action start >/dev/null; \
	fi; \
	status=failed; \
	trap 'if [[ "$$timing_enabled" -eq 1 ]]; then python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage package_build --action end --status "$$status" >/dev/null || true; fi' EXIT; \
	./scripts/foundry/sync_hosted_source.sh; \
	(cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd package --no-prompt); \
	status=succeeded

foundry-provision:
	@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "Set FOUNDRY_FULL_INFRA_AUTHORIZED=true after reviewed preview approval." >&2; exit 2; }
	./scripts/foundry/bootstrap_azd_env.sh
	$(MAKE) foundry-iac-build
	$(MAKE) foundry-capacity-preflight-full
	$(MAKE) foundry-provision-ready
	FOUNDRY_BOOTSTRAP_HYDRATE=1 ./scripts/foundry/bootstrap_azd_env.sh

foundry-provision-preview:
	FOUNDRY_PREVIEW_MODE=full_infra FOUNDRY_DEPLOYMENT_PROFILE="$(FOUNDRY_DEPLOYMENT_PROFILE)" ./scripts/foundry/preview_public_infrastructure.sh

foundry-reuse-preview:
	FOUNDRY_PREVIEW_MODE=reuse FOUNDRY_DEPLOYMENT_PROFILE="$(FOUNDRY_DEPLOYMENT_PROFILE)" ./scripts/foundry/preview_public_infrastructure.sh

foundry-provision-ready:
	@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "Full infrastructure apply is not authorized." >&2; exit 2; }
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/ensure_foundry_azd_defaults.sh
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt $(if $(FOUNDRY_PROVISION_NO_STATE),--no-state,)

foundry-postgres-schema:
	@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "PostgreSQL schema mutation requires full infrastructure authority." >&2; exit 2; }
	./scripts/foundry/bootstrap_postgres_schema.sh

foundry-postgres-credentials:
	@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "PostgreSQL credential mutation requires full infrastructure authority." >&2; exit 2; }
	./scripts/foundry/provision_postgres_runtime_credentials.sh

foundry-backend-deploy: foundry-postgres-readiness
	$(MAKE) foundry-backend-deploy-ready

foundry-backend-deploy-ready: foundry-python-wheelhouse
	@set -euo pipefail; \
	timing_enabled=0; \
	if [[ -n "$${FOUNDRY_RELEASE_ID:-}" ]]; then timing_enabled=1; python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage backend_deployment --action start >/dev/null; fi; \
	status=failed; \
	trap 'if [[ "$$timing_enabled" -eq 1 ]]; then python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage backend_deployment --action end --status "$$status" >/dev/null || true; fi' EXIT; \
	./scripts/foundry/deploy_public_backend.sh; \
	status=succeeded

foundry-frontend-deploy:
	$(MAKE) foundry-frontend-deploy-ready

foundry-frontend-deploy-ready:
	@set -euo pipefail; \
	timing_enabled=0; \
	if [[ -n "$${FOUNDRY_RELEASE_ID:-}" ]]; then timing_enabled=1; python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage frontend_deployment --action start >/dev/null; fi; \
	status=failed; \
	trap 'if [[ "$$timing_enabled" -eq 1 ]]; then python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage frontend_deployment --action end --status "$$status" >/dev/null || true; fi' EXIT; \
	./scripts/foundry/deploy_public_frontend.sh; \
	status=succeeded

foundry-app-deploy: foundry-python-wheelhouse
	$(MAKE) foundry-postgres-readiness
	$(MAKE) -j2 foundry-backend-deploy-ready foundry-frontend-deploy-ready

foundry-deploy: foundry-postgres-readiness foundry-python-wheelhouse
	$(MAKE) foundry-package
	FOUNDRY_PREFLIGHT_SCOPE=hosted $(MAKE) foundry-model-preflight
	$(MAKE) foundry-runtime-connection-ready
	$(MAKE) foundry-deploy-ready

foundry-deploy-ready: foundry-python-wheelhouse
	@set -euo pipefail; \
	timing_enabled=0; \
	if [[ -n "$${FOUNDRY_RELEASE_ID:-}" ]]; then timing_enabled=1; python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage hosted_deployment_activation --action start >/dev/null; fi; \
	status=failed; \
	trap 'if [[ "$$timing_enabled" -eq 1 ]]; then python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage hosted_deployment_activation --action end --status "$$status" >/dev/null || true; fi' EXIT; \
	test -f backend/Dockerfile.hosted; \
	test -f backend/foundry/main.py; \
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/deploy_hosted_container.sh; \
	status=succeeded

foundry-release-deploy: foundry-python-wheelhouse
	@if [[ "$${PUBLIC_RELEASE_PREREQUISITES_PASSED:-}" != "true" ]]; then \
		$(MAKE) foundry-release-preflight; \
	fi
	$(MAKE) foundry-package
	$(MAKE) foundry-runtime-connection-check
	$(MAKE) -j3 foundry-deploy-ready foundry-backend-deploy-ready foundry-frontend-deploy-ready

foundry-up: foundry-python-wheelhouse
	$(MAKE) foundry-provision
	$(MAKE) foundry-release-deploy
	$(MAKE) foundry-appinsights-connection

foundry-smoke:
	./scripts/foundry/hosted_smoke.sh

foundry-postgres-readiness:
	./scripts/foundry/check_public_postgres_readiness.sh

foundry-model-preflight:
	FOUNDRY_CAPACITY_MODE=app_only ./scripts/foundry/preflight_models.sh

foundry-capacity-preflight-full:
	FOUNDRY_CAPACITY_MODE=full_infra ./scripts/foundry/preflight_models.sh

foundry-evaluator-rbac-check:
	./scripts/foundry/verify_evaluator_rbac.sh

foundry-release-preflight:
	$(MAKE) -j2 foundry-model-preflight foundry-reuse-preview
	$(MAKE) -j3 foundry-postgres-readiness foundry-runtime-connection-check foundry-evaluator-rbac-check

foundry-runtime-connection:
	@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "Runtime connection mutation requires full infrastructure authority." >&2; exit 2; }
	$(MAKE) foundry-postgres-readiness
	$(MAKE) foundry-runtime-connection-ready

foundry-runtime-connection-ready:
	@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "Runtime connection mutation requires full infrastructure authority." >&2; exit 2; }
	az bicep build --file infra/foundry-hosted/iac/modules/foundry-project-runtime-secret-connection.bicep --stdout >/dev/null
	./scripts/foundry/converge_runtime_secret_connection.sh

foundry-runtime-connection-check:
	./scripts/foundry/verify_runtime_secret_connection.sh

foundry-hosted-rbac:
	@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "Hosted RBAC mutation requires full infrastructure authority." >&2; exit 2; }
	./scripts/foundry/ensure_hosted_agent_rbac.sh

foundry-hosted-e2e:
	./scripts/foundry/hosted_e2e.sh

foundry-appinsights-connection:
	./scripts/foundry/verify_project_appinsights_connection.sh

foundry-telemetry:
	./scripts/foundry/verify_telemetry.sh

foundry-verify:
	./scripts/foundry/verify_deployment.sh

foundry-evidence: ensure-backend-env
	@test -n "$${FOUNDRY_RELEASE_ID:-}" || { echo "FOUNDRY_RELEASE_ID is required." >&2; exit 2; }
	@set -euo pipefail; \
	python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage final_evidence --action start >/dev/null; \
	status=failed; \
	trap 'python3 scripts/foundry/release_evidence.py timing --release-id "$${FOUNDRY_RELEASE_ID}" --stage final_evidence --action end --status "$$status" >/dev/null || true' EXIT; \
	PYTHONPATH=. backend/.venv/bin/python scripts/foundry/release_evidence.py aggregate --release-id "$${FOUNDRY_RELEASE_ID}"; \
	status=succeeded
	PYTHONPATH=. backend/.venv/bin/python scripts/foundry/release_evidence.py finalize --release-id "$${FOUNDRY_RELEASE_ID}" --status succeeded

foundry-release-migration-plan:
	python3 scripts/foundry/release_migration.py

TEAMS_PUBLISH_SCOPE ?= Shared
TEAMS_PUBLICATION_MANIFEST ?= infra/foundry-hosted/teams-publication.json
TEAMS_PUBLICATION_ARGS ?=

foundry-activity-plan:
	@python3 ./scripts/foundry/reconcile_activity_endpoint.py plan --publish-scope "$(TEAMS_PUBLISH_SCOPE)"

foundry-activity-apply:
	@python3 ./scripts/foundry/reconcile_activity_endpoint.py apply --publish-scope "$(TEAMS_PUBLISH_SCOPE)"

foundry-activity-rollback:
	@python3 ./scripts/foundry/reconcile_activity_endpoint.py rollback --publish-scope "$(TEAMS_PUBLISH_SCOPE)"

foundry-teams-plan:
	@python3 ./scripts/foundry/publish_teams_agent.py plan --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-preview:
	@python3 ./scripts/foundry/publish_teams_agent.py preview-bot --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-deploy-bot:
	@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "Set FOUNDRY_FULL_INFRA_AUTHORIZED=true after reviewed Teams what-if approval." >&2; exit 2; }
	@python3 ./scripts/foundry/publish_teams_agent.py deploy-bot --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-package:
	@python3 ./scripts/foundry/publish_teams_agent.py package --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-publish:
	@python3 ./scripts/foundry/publish_teams_agent.py publish --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-verify-local-state:
	@python3 ./scripts/foundry/publish_teams_agent.py verify-local-state --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-rollback-plan:
	@python3 ./scripts/foundry/publish_teams_agent.py rollback-plan --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-release: foundry-python-wheelhouse
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/deploy_public_dev.sh

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache \
		scripts/playwright/test-results scripts/playwright/playwright-report \
		frontend/test-results frontend/playwright-report
