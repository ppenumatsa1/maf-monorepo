SHELL := /bin/bash
COMPOSE_ENV_FILE ?= backend/.env.example

.PHONY: help bootstrap venv-backend install-backend install-frontend ensure-backend-env ensure-test-postgres \
	ensure-frontend ensure-playwright run-backend run-frontend format format-check lint test test-backend test-backend-run \
	eval-backend eval-backend-run eval-foundry eval-foundry-deployed eval-all test-e2e test-e2e-run test-e2e-selected manual-matrix \
	parity-all run-mock-mcp up down logs ps docker-test validate-quick validate-full bicep-build release-source-validation \
	release-preflight release-app release-app-dry-run release-validate release-infra-preview release-infra-reconcile \
	release-infra-mock-test build-release-images deploy-ci-images deploy-app deploy-full clean

help:
	@echo "Available targets:"
	@echo "  up/down/logs/ps  - Manage the local Docker parity stack"
	@echo "  bootstrap        - Install backend, frontend, and Playwright dependencies"
	@echo "  test             - Run backend lint and tests"
	@echo "  eval-backend     - Run deterministic workflow contract evaluation"
	@echo "  eval-foundry     - Run report-only Foundry low/high-risk evaluation"
	@echo "  eval-foundry-deployed - Run the Foundry evaluation against the selected AZD backend URL"
	@echo "  test-e2e-selected - Run focused selected-thread Playwright coverage"
	@echo "  test-e2e         - Run all workflow and selected-thread Playwright tests"
	@echo "  docker-test      - Optional local Docker Compose E2E; cloud CI is authoritative"
	@echo "  build-release-images - Build the exact backend/frontend images selected by BACKEND_IMAGE and FRONTEND_IMAGE"
	@echo "  parity-all       - Run fast local and Azure app-hosted parity checks"
	@echo "  release-app      - Preflight and deploy app revisions only (the default release path)"
	@echo "  release-validate - Smoke, hosted E2E/eval, then verify fresh App Insights evidence"
	@echo "  release-infra-preview - Guarded owner-reviewed infrastructure what-if; never deploys"
	@echo "  release-infra-reconcile - Guarded owner-confirmed infrastructure reconciliation"

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
	@DATABASE_URL="$${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/maf_workflow?sslmode=disable}" \
		./scripts/local/ensure_test_postgres.sh

run-backend: ensure-backend-env
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

run-frontend:
	cd frontend && npm run dev

format: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff format .

format-check: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff format --check .

lint: ensure-backend-env
	cd backend && . .venv/bin/activate && ruff check .

test: lint test-backend

test-backend:
	./scripts/local/run-with-isolated-postgres.sh -- $(MAKE) test-backend-run

test-backend-run: ensure-backend-env ensure-test-postgres
	cd backend && . .venv/bin/activate && pytest -q

eval-backend:
	./scripts/local/run-with-isolated-postgres.sh -- $(MAKE) eval-backend-run

eval-backend-run: ensure-backend-env ensure-test-postgres
	cd backend && . .venv/bin/activate && python -m evals.eval_runner

eval-foundry: ensure-backend-env
	cd backend && . .venv/bin/activate && python -m evals.foundry_eval_runner

eval-foundry-deployed:
	@set -euo pipefail; \
	environment="$${AZURE_ENV_NAME:-maf-ora-azure}"; \
	get_value() { AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$$1" --environment "$$environment"; }; \
	api_url="$$(get_value API_URL)"; \
	project_endpoint="$$(get_value FOUNDRY_PROJECTS_ENDPOINT)"; \
	model_name="$$(get_value FOUNDRY_MODEL_DEPLOYMENT_NAME)"; \
	eval_model="$$(get_value FOUNDRY_EVAL_MODEL)"; \
	[[ -n "$$api_url" && -n "$$project_endpoint" && -n "$$model_name" && -n "$$eval_model" ]] || { echo "Selected AZD environment is missing deployed Foundry evaluation configuration."; exit 1; }; \
	FOUNDRY_EVAL_API_URL="$$api_url" \
	FOUNDRY_PROJECTS_ENDPOINT="$$project_endpoint" \
	FOUNDRY_MODEL_DEPLOYMENT_NAME="$$model_name" \
	FOUNDRY_EVAL_MODEL="$$eval_model" \
	$(MAKE) eval-foundry

eval-all: eval-backend eval-foundry

ensure-playwright:
	@if [[ ! -x scripts/playwright/node_modules/.bin/playwright ]]; then \
		cd scripts/playwright && npm ci; \
	fi

ensure-frontend:
	@if [[ ! -x frontend/node_modules/.bin/vite ]]; then \
		cd frontend && npm ci; \
	fi

test-e2e:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		$(MAKE) test-e2e-run; \
	else \
		PLAYWRIGHT_E2E_SUITE="$${PLAYWRIGHT_E2E_SUITE:-all}" \
			./scripts/local/run-with-isolated-postgres.sh -- $(MAKE) test-e2e-run; \
	fi

test-e2e-selected:
	PLAYWRIGHT_E2E_SUITE=selected-thread $(MAKE) test-e2e

test-e2e-run: ensure-frontend ensure-playwright
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		./scripts/playwright/run-e2e-suite.sh "$${PLAYWRIGHT_BASE_URL}" "$${PLAYWRIGHT_E2E_SUITE:-all}"; \
	else \
		$(MAKE) ensure-backend-env ensure-test-postgres; \
		backend_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
		backend_url="http://127.0.0.1:$${backend_port}"; \
		artifacts_dir="$$(pwd)/.artifacts/local-e2e-$${backend_port}"; \
		mkdir -p "$${artifacts_dir}"; \
		backend_log="$${artifacts_dir}/backend.log"; \
		( \
			cd backend && . .venv/bin/activate && \
			APP_ENV=local \
			WORKFLOW_MODE=maf_sdk \
			STORE_PROVIDER=postgres \
			MEMORY_PROVIDER=postgres \
			MCP_SERVER_URL= \
			uvicorn app.main:app --host 127.0.0.1 --port "$${backend_port}" \
		) > "$${backend_log}" 2>&1 & \
		backend_pid="$$!"; \
		frontend_port="$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"; \
		frontend_url="http://127.0.0.1:$${frontend_port}"; \
		frontend_log="$${artifacts_dir}/frontend.log"; \
		cleanup() { \
			for pid in "$${backend_pid:-}" "$${frontend_pid:-}"; do \
				[[ -n "$${pid}" ]] && kill "$${pid}" 2>/dev/null || true; \
			done; \
			for _ in {1..20}; do \
				alive=0; \
				for pid in "$${backend_pid:-}" "$${frontend_pid:-}"; do \
					[[ -n "$${pid}" ]] && kill -0 "$${pid}" 2>/dev/null && alive=1; \
				done; \
				[[ "$${alive}" -eq 0 ]] && break; \
				sleep 0.25; \
			done; \
			for pid in "$${backend_pid:-}" "$${frontend_pid:-}"; do \
				[[ -n "$${pid}" ]] && kill -0 "$${pid}" 2>/dev/null && kill -KILL "$${pid}" 2>/dev/null || true; \
			done; \
			wait "$${backend_pid:-}" 2>/dev/null || true; \
			wait "$${frontend_pid:-}" 2>/dev/null || true; \
		}; \
		trap cleanup EXIT; \
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
		for _ in {1..30}; do curl -fsS "$${frontend_url}" >/dev/null && break; sleep 1; done; \
		proxy_health="$$(curl -fsS "$${frontend_url}/api/health" 2>/dev/null || true)"; \
		if [[ "$${proxy_health}" != *'"workflow_mode":"maf_sdk"'* || "$${proxy_health}" != *'"environment":"local"'* ]]; then \
			echo "Frontend proxy is not targeting the isolated local backend. See $${frontend_log}"; \
			exit 1; \
		fi; \
		PLAYWRIGHT_ARTIFACTS_DIR="$${artifacts_dir}" ./scripts/playwright/run-e2e-suite.sh "$${frontend_url}" "$${PLAYWRIGHT_E2E_SUITE:-all}"; \
		e2e_status="$$?"; \
		cleanup; \
		trap - EXIT; \
		exit "$${e2e_status}"; \
	fi

manual-matrix:
	scripts/manual/run-manual-matrix.sh "$${API_URL:-http://localhost:8000}" $${MANUAL_MATRIX_ARGS:-}

parity-all:
	scripts/parity/run-parity-matrix.sh --targets local azure --profile fast

run-mock-mcp: ensure-backend-env
	. backend/.venv/bin/activate && uvicorn scripts.mcp.mock_mcp_server:app --reload --port 8011

up:
	docker compose --env-file $(COMPOSE_ENV_FILE) up --build -d backend frontend mock-mcp
	@echo "Frontend: http://localhost:5173"
	@echo "Backend health: http://localhost:8000/health"

down:
	docker compose --env-file $(COMPOSE_ENV_FILE) down --remove-orphans

logs:
	docker compose --env-file $(COMPOSE_ENV_FILE) logs -f --tail=200

ps:
	docker compose --env-file $(COMPOSE_ENV_FILE) ps

docker-test: ensure-frontend ensure-playwright
	@set -euo pipefail; \
	build_args=(); \
	if [[ -z "$${BACKEND_IMAGE:-}" || -z "$${FRONTEND_IMAGE:-}" ]]; then \
		build_args+=(--build); \
	fi; \
	readarray -t ports < <(python3 -c 'import socket; sockets=[socket.socket() for _ in range(4)]; [s.bind(("127.0.0.1", 0)) for s in sockets]; print(*[s.getsockname()[1] for s in sockets], sep="\n"); [s.close() for s in sockets]'); \
	project="maf-docker-e2e-$$(date +%s)-$$RANDOM"; \
	artifacts_dir=".artifacts/$${project}"; \
	mkdir -p "$${artifacts_dir}"; \
	cleanup() { \
		docker compose --project-name "$${project}" --env-file $(COMPOSE_ENV_FILE) --profile test down --volumes --remove-orphans >/dev/null 2>&1 || true; \
	}; \
	trap cleanup EXIT; \
	POSTGRES_PORT="$${ports[0]}" \
	MOCK_MCP_PORT="$${ports[1]}" \
	BACKEND_PORT="$${ports[2]}" \
	FRONTEND_PORT="$${ports[3]}" \
	PLAYWRIGHT_ARTIFACTS_DIR="/workspace/$${artifacts_dir}" \
	docker compose --project-name "$${project}" --env-file $(COMPOSE_ENV_FILE) --profile test up "$${build_args[@]}" --abort-on-container-exit --exit-code-from playwright playwright

build-release-images:
	@set -euo pipefail; \
	[[ -n "$${BACKEND_IMAGE:-}" ]] || { echo "BACKEND_IMAGE is required."; exit 1; }; \
	[[ -n "$${FRONTEND_IMAGE:-}" ]] || { echo "FRONTEND_IMAGE is required."; exit 1; }; \
	docker build --tag "$${BACKEND_IMAGE}" backend; \
	docker build --tag "$${FRONTEND_IMAGE}" frontend

deploy-ci-images:
	./scripts/release/deploy-ci-images.sh

validate-quick:
	@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then $(MAKE) test-e2e; \
	elif [[ -n "$${WEB_URL:-}" ]]; then PLAYWRIGHT_BASE_URL="$${WEB_URL}" $(MAKE) test-e2e; \
	else $(MAKE) test-e2e; fi
	@if [[ -n "$${API_URL:-}" ]]; then infra/azure-apphosted/runtime/smoke-test.sh "$${API_URL}" "$${WEB_URL:-}"; fi

validate-full:
	$(MAKE) test
	$(MAKE) eval-backend
	$(MAKE) test-e2e-selected
	$(MAKE) test-e2e
	./scripts/skills/design-review-skill.sh

bicep-build:
	bicep build infra/azure-apphosted/iac/main.bicep --stdout >/dev/null

release-source-validation:
	./scripts/release/validate-release-assets.sh
	./scripts/release/test-reconcile-infrastructure-approval.sh

release-preflight:
	@$(MAKE) --no-print-directory -j2 release-source-validation bicep-build

release-app: release-preflight
	./scripts/release/deploy-app-only.sh

release-app-dry-run: release-preflight
	RELEASE_DRY_RUN=true ./scripts/release/deploy-app-only.sh

release-validate:
	./scripts/release/validate-hosted-release.sh

release-infra-preview:
	./scripts/release/run-reconcile-infrastructure.sh --preview

release-infra-reconcile:
	./scripts/release/run-reconcile-infrastructure.sh --apply

release-infra-mock-test:
	./scripts/release/test-reconcile-infrastructure-approval.sh

deploy-app: release-app

deploy-full:
	@echo "Full deployment is disabled. Normal releases are app-only; use the explicitly owner-confirmed release-infra-reconcile target only when required." >&2
	@exit 1

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf backend/.pytest_cache scripts/playwright/test-results scripts/playwright/playwright-report .artifacts
