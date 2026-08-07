SHELL := /bin/bash
COMPOSE_ENV_FILE ?= $(if $(wildcard backend/.env),backend/.env,backend/.env.example)

.PHONY: help bootstrap venv-backend install-backend install-frontend ensure-backend-env ensure-test-postgres \
	run-backend run-frontend format lint test test-backend eval-backend eval-foundry eval-foundry-config eval-all test-e2e manual-matrix \
	test-e2e-selected-thread \
	run-mock-mcp up down logs ps docker-test \
	validate-quick validate-full clean \
	foundry-bootstrap foundry-iac-build foundry-package foundry-up foundry-provision foundry-provision-ready \
	foundry-postgres-readiness foundry-backend-deploy foundry-backend-deploy-ready \
	foundry-frontend-deploy foundry-frontend-deploy-ready foundry-app-deploy \
	foundry-deploy foundry-deploy-ready foundry-release-deploy foundry-smoke \
	foundry-hosted-e2e foundry-appinsights-connection foundry-telemetry foundry-release

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
	@echo "  foundry-bootstrap - Refresh local AZD defaults for the existing public target"
	@echo "  foundry-iac-build - Compile the public Foundry Bicep template"
	@echo "  foundry-package - Freshly sync hosted source and validate AZD packaging"
	@echo "  foundry-provision - Apply the approved full infrastructure route"
	@echo "  foundry-app-deploy - Verify readiness once, then deploy backend and frontend concurrently"
	@echo "  foundry-deploy  - Verify readiness, package, and deploy the hosted agent"
	@echo "  foundry-release-deploy - Package, verify readiness once, and deploy all runtime legs concurrently"
	@echo "  foundry-smoke   - Invoke hosted agent health check via responses protocol"
	@echo "  foundry-hosted-e2e - Run hosted Responses low/high-risk and approval-resume checks"
	@echo "  foundry-eval    - Run the report-only Foundry trace-evaluation gate"
	@echo "  foundry-telemetry - Verify Application Insights after hosted E2E evidence exists"
	@echo "  foundry-release - Run the authenticated, gated public release DAG"
	@echo "  clean           - Remove caches and test artifacts"

bootstrap: install-backend install-frontend

venv-backend:
	cd backend && python3 -m venv .venv

install-backend: venv-backend
	cd backend && . .venv/bin/activate && pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install
	cd scripts/playwright && npm install

ensure-backend-env:
	test -d backend/.venv || $(MAKE) venv-backend
	. backend/.venv/bin/activate && python -c "import pytest" >/dev/null 2>&1 || $(MAKE) install-backend

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

test-e2e:
	@set -euo pipefail; \
	if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd scripts/playwright && npm run test:e2e; \
		PLAYWRIGHT_BASE_URL="$${PLAYWRIGHT_BASE_URL}" $(MAKE) test-e2e-selected-thread; \
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
		PLAYWRIGHT_BASE_URL="$${frontend_url}" $(MAKE) test-e2e-selected-thread; \
	fi

manual-matrix:
	scripts/manual/run-manual-matrix.sh "$${API_URL:-http://localhost:8000}" $${MANUAL_MATRIX_ARGS:-}

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
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/ensure_foundry_azd_defaults.sh

foundry-iac-build:
	az bicep build --file infra/foundry-hosted/iac/main.bicep

foundry-package:
	./scripts/foundry/sync_hosted_source.sh
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd package --no-prompt

foundry-provision:
	@if [[ "$${FOUNDRY_INFRA_RECONCILIATION_APPROVED:-false}" != "true" || -z "$${FOUNDRY_INFRA_RECONCILIATION_REFERENCE:-}" ]]; then \
		echo "Refusing provision: set FOUNDRY_INFRA_RECONCILIATION_APPROVED=true and a non-secret FOUNDRY_INFRA_RECONCILIATION_REFERENCE after review."; \
		exit 2; \
	fi
	$(MAKE) foundry-iac-build
	$(MAKE) foundry-provision-ready

foundry-provision-ready:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/ensure_foundry_azd_defaults.sh
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt $(if $(FOUNDRY_PROVISION_NO_STATE),--no-state,)

foundry-backend-deploy: foundry-postgres-readiness
	$(MAKE) foundry-backend-deploy-ready

foundry-backend-deploy-ready:
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy backend --no-prompt

foundry-frontend-deploy:
	$(MAKE) foundry-frontend-deploy-ready

foundry-frontend-deploy-ready:
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy frontend --no-prompt

foundry-app-deploy:
	$(MAKE) foundry-postgres-readiness
	$(MAKE) -j2 foundry-backend-deploy-ready foundry-frontend-deploy-ready

foundry-deploy: foundry-postgres-readiness
	$(MAKE) foundry-package
	$(MAKE) foundry-deploy-ready

foundry-deploy-ready:
	@test -f backend/Dockerfile.hosted
	@test -f backend/foundry/main.py
	@AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/deploy_hosted_container.sh

foundry-release-deploy:
	$(MAKE) foundry-package
	$(MAKE) foundry-postgres-readiness
	$(MAKE) -j3 foundry-backend-deploy-ready foundry-frontend-deploy-ready foundry-deploy-ready

foundry-up:
	$(MAKE) foundry-provision
	$(MAKE) foundry-release-deploy
	$(MAKE) foundry-appinsights-connection

foundry-smoke:
	@if [[ -n "$${SMOKE_THREAD_ID:-}" ]]; then \
		cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke order-resolution-hosted "$${SMOKE_MESSAGE:-Resolve delayed order ORD-1009}" --protocol responses --conversation-id "$${SMOKE_THREAD_ID}" --no-prompt; \
	else \
		cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke order-resolution-hosted "$${SMOKE_MESSAGE:-Resolve delayed order ORD-1009}" --protocol responses --new-conversation --new-session --no-prompt; \
	fi

foundry-postgres-readiness:
	./scripts/foundry/check_public_postgres_readiness.sh

foundry-hosted-e2e:
	./scripts/foundry/hosted_e2e.sh

foundry-appinsights-connection:
	./scripts/foundry/verify_project_appinsights_connection.sh

foundry-telemetry:
	./scripts/foundry/verify_telemetry.sh

foundry-release:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/deploy_public_dev.sh

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache \
		scripts/playwright/test-results scripts/playwright/playwright-report \
		frontend/test-results frontend/playwright-report
