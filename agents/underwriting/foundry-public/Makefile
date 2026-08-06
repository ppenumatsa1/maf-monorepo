SHELL := /bin/bash
.RECIPEPREFIX := >
ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
VENV := $(ROOT).venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
ENV_FILE := $(ROOT).env
E2E_LOG_DIR := $(ROOT)backend/.tmp/e2e
FOUNDRY_RUNTIME_SMOKE := ./infra/foundry-hosted/runtime/smoke-test.sh

ifneq ("$(wildcard $(ENV_FILE))","")
include $(ENV_FILE)
export
endif

.PHONY: help bootstrap up down logs db-reset install run run-fail-once run-crash resume state events checkpoints \
	backend-dev frontend-install frontend-dev \
	test test-backend test-frontend test-scripts test-e2e \
	lint lint-backend lint-frontend format format-check quality validate-quick validate-full \
	foundry-bootstrap foundry-iac-build foundry-provision foundry-postgres-rebuild foundry-postgres-schema \
	foundry-postgres-credentials foundry-postgres-readiness foundry-backend-deploy foundry-frontend-deploy \
	foundry-backend-deploy-ready foundry-deploy-ready foundry-app-deploy foundry-release-deploy foundry-deploy \
	foundry-up foundry-smoke foundry-hosted-e2e foundry-eval \
	foundry-appinsights-connection foundry-telemetry foundry-release

CRASH_TARGET ?= medical_check
SMOKE_MODE ?= happy

help:
>@printf "Primary local commands:\n"
>@printf "  make bootstrap                    - Install Python and frontend dependencies\n"
>@printf "  make up                           - Start local postgres, backend, and frontend\n"
>@printf "  make down                         - Stop local containers\n"
>@printf "  make logs                         - Tail frontend/backend/postgres logs\n"
>@printf "  make install                      - Create .venv and install Python dependencies\n"
>@printf "  make frontend-install             - Install frontend dependencies\n"
>@printf "  make db-reset                     - Reset local database schema\n"
>@printf "  make run                          - Run happy-path underwriting workflow\n"
>@printf "  make run-fail-once                - Run with one retryable failure injected\n"
>@printf "  make run-crash                    - Crash after CRASH_TARGET (default: medical_check)\n"
>@printf "  make resume                       - Resume workflow (RUN_ID required)\n"
>@printf "  make state                        - Show persisted workflow state (RUN_ID required)\n"
>@printf "  make events                       - Show workflow events (RUN_ID required)\n"
>@printf "  make checkpoints                  - Show MAF checkpoints (RUN_ID required)\n"
>@printf "  make lint                         - Run backend + frontend lint checks\n"
>@printf "  make format                       - Format backend code\n"
>@printf "  make quality                      - Run lint + format-check + unit/script tests\n"
>@printf "  make validate-quick               - Run the quick validation lane\n"
>@printf "  make validate-full                - Run the full validation lane\n"
>@printf "  make test                         - Run backend + frontend tests\n"
>@printf "  make test-scripts                 - Run Foundry helper script tests\n"
>@printf "  make test-e2e                     - Run Playwright end-to-end tests\n"
>@printf "\nFoundry public release commands:\n"
>@printf "  make foundry-bootstrap            - Refresh the local azd environment from the reused Azure resources\n"
>@printf "  make foundry-iac-build            - Compile resource-reuse Foundry Bicep\n"
>@printf "  make foundry-provision            - Apply approved PostgreSQL auth/firewall and Foundry connection IaC\n"
>@printf "  make foundry-postgres-rebuild CONFIRM=REBUILD-azpgwhcedyxchnbtmpub\n"
>@printf "                                     Delete and recreate the fixed PostgreSQL server\n"
>@printf "  make foundry-postgres-schema      - Create or migrate the PostgreSQL schema with the administrator credential\n"
>@printf "  make foundry-postgres-credentials - Provision or rotate the local-only PostgreSQL runtime credential\n"
>@printf "  make foundry-postgres-readiness   - Verify PostgreSQL TLS, auth, firewall, and runtime credential readiness\n"
>@printf "  make foundry-backend-deploy       - Build and deploy the public backend wrapper\n"
>@printf "  make foundry-frontend-deploy      - Build and deploy the public operations console\n"
>@printf "  make foundry-app-deploy           - Verify shared readiness, then deploy public apps concurrently\n"
>@printf "  make foundry-deploy               - Build and deploy the hosted underwriting agent\n"
>@printf "  make foundry-release-deploy       - Verify shared readiness, then deploy public apps and hosted agent concurrently\n"
>@printf "  make foundry-up                   - Provision, deploy all release components concurrently, and verify App Insights connection\n"
>@printf "  make foundry-smoke                - Run direct hosted-agent smoke and write trace-eval evidence\n"
>@printf "  make foundry-hosted-e2e           - Run hosted API smoke plus deployed Playwright E2E\n"
>@printf "  make foundry-eval                 - Run the report-only Foundry trace evaluation gate\n"
>@printf "  make foundry-appinsights-connection - Verify the Foundry project App Insights connection\n"
>@printf "  make foundry-telemetry            - Verify App Insights evidence for hosted E2E run IDs\n"
>@printf "  make foundry-release              - Route validation/deployment and run the public release sequence\n"

bootstrap: install frontend-install

up:
>cd $(ROOT) && docker compose up -d --build postgres backend frontend

down:
>cd $(ROOT) && docker compose down

logs:
>cd $(ROOT) && docker compose logs -f frontend backend postgres

backend-dev:
>cd $(ROOT) && PYTHONPATH=$(ROOT)/backend $(VENV)/bin/uvicorn app.server:app --host 0.0.0.0 --port 8000

install:
>cd $(ROOT) && python3 -m venv .venv
>cd $(ROOT) && $(PIP) install --upgrade pip setuptools wheel
>cd $(ROOT) && $(PIP) install -e ".[dev]"
>cd $(ROOT) && $(PY) -c "import agent_framework; print('agent_framework import OK')"

frontend-install:
>cd $(ROOT)/frontend && npm install

db-reset:
>cd $(ROOT) && $(PY) -m app.main db-reset

run:
>cd $(ROOT) && $(PY) -m app.main run

run-fail-once:
>cd $(ROOT) && FAIL_RISK_ONCE=true $(PY) -m app.main run

run-crash:
>cd $(ROOT) && CRASH_AFTER_EXECUTOR=$(CRASH_TARGET) $(PY) -m app.main run

resume:
>cd $(ROOT) && $(PY) -m app.main resume --run-id "$(RUN_ID)"

state:
>cd $(ROOT) && $(PY) -m app.main state --run-id "$(RUN_ID)"

events:
>cd $(ROOT) && $(PY) -m app.main events --run-id "$(RUN_ID)"

checkpoints:
>cd $(ROOT) && $(PY) -m app.main checkpoints --run-id "$(RUN_ID)"

test:
>cd $(ROOT) && $(MAKE) test-backend
>cd $(ROOT) && $(MAKE) test-frontend

test-backend:
>@set -euo pipefail; \
	postgres_port="$${TEST_POSTGRES_HOST_PORT:-$$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')}"; \
	compose_project="$${TEST_COMPOSE_PROJECT_NAME:-underwriting-test-$${postgres_port}}"; \
	cleanup() { \
		COMPOSE_PROJECT_NAME="$$compose_project" POSTGRES_HOST_PORT="$$postgres_port" docker compose down --remove-orphans >/dev/null 2>&1 || true; \
	}; \
	trap cleanup EXIT; \
	COMPOSE_PROJECT_NAME="$$compose_project" POSTGRES_HOST_PORT="$$postgres_port" docker compose up -d postgres; \
	until COMPOSE_PROJECT_NAME="$$compose_project" POSTGRES_HOST_PORT="$$postgres_port" docker compose exec -T postgres pg_isready -U underwriting -d underwriting >/dev/null; do sleep 1; done; \
	DATABASE_URL="postgresql+psycopg://underwriting:underwriting@localhost:$$postgres_port/underwriting?sslmode=disable" \
		PYTHONPATH="$(ROOT)/backend" "$(PYTEST)"

test-frontend:
>cd $(ROOT)/frontend && npm run test

test-scripts:
>cd $(ROOT) && PYTHONPATH="$(ROOT)/backend" "$(PYTEST)" scripts/foundry/tests/test_postgres_runtime_credentials.py

test-e2e:
>@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		cd $(ROOT)/frontend && npm run test:e2e; \
	else \
		set -euo pipefail; \
		mkdir -p "$(E2E_LOG_DIR)"; \
		postgres_port="$${E2E_POSTGRES_HOST_PORT:-5434}"; \
		backend_port="$${E2E_BACKEND_HOST_PORT:-8000}"; \
		backend_log="$${E2E_LOG_FILE:-$(E2E_LOG_DIR)/underwriting-e2e-backend.log}"; \
		compose_project="$${E2E_COMPOSE_PROJECT_NAME:-underwriting-e2e-$${postgres_port}}"; \
		cleanup() { \
			if [[ -n "$${backend_pid:-}" ]]; then kill "$$backend_pid" 2>/dev/null || true; wait "$$backend_pid" 2>/dev/null || true; fi; \
			COMPOSE_PROJECT_NAME="$$compose_project" POSTGRES_HOST_PORT="$$postgres_port" docker compose down --remove-orphans >/dev/null 2>&1 || true; \
		}; \
		trap cleanup EXIT; \
		COMPOSE_PROJECT_NAME="$$compose_project" POSTGRES_HOST_PORT="$$postgres_port" docker compose up -d postgres; \
		until COMPOSE_PROJECT_NAME="$$compose_project" POSTGRES_HOST_PORT="$$postgres_port" docker compose exec -T postgres pg_isready -U underwriting -d underwriting >/dev/null; do sleep 1; done; \
		DATABASE_URL="postgresql+psycopg://underwriting:underwriting@localhost:$$postgres_port/underwriting?sslmode=disable" \
			FRONTEND_ORIGIN="http://127.0.0.1:4175" \
			UNDERWRITING_EXECUTION_MODE=local \
			PYTHONPATH="$(ROOT)/backend" "$(VENV)/bin/uvicorn" app.server:app --host 127.0.0.1 --port "$$backend_port" > "$$backend_log" 2>&1 & \
		backend_pid="$$!"; \
		until curl -fsS "http://127.0.0.1:$$backend_port/health" >/dev/null; do sleep 1; done; \
		cd $(ROOT)/frontend && npm run test:e2e; \
	fi

lint:
>cd $(ROOT) && $(MAKE) lint-backend
>cd $(ROOT) && $(MAKE) lint-frontend

lint-backend:
>cd $(ROOT) && $(RUFF) check backend

lint-frontend:
>cd $(ROOT)/frontend && npm run lint

format:
>cd $(ROOT) && $(RUFF) format backend

format-check:
>cd $(ROOT) && $(RUFF) format --check backend

quality:
>cd $(ROOT) && $(MAKE) lint
>cd $(ROOT) && $(MAKE) format-check
>cd $(ROOT) && $(MAKE) test
>cd $(ROOT) && $(MAKE) test-scripts

validate-quick:
>@if [[ -n "$${PLAYWRIGHT_BASE_URL:-}" ]]; then \
		$(MAKE) test-e2e; \
	elif [[ -n "$${WEB_URL:-}" ]]; then \
		PLAYWRIGHT_BASE_URL="$$WEB_URL" $(MAKE) test-e2e; \
	else \
		$(MAKE) test-e2e; \
	fi

validate-full:
>$(MAKE) lint
>$(MAKE) format-check
>$(MAKE) test
>$(MAKE) test-scripts
>$(MAKE) test-e2e

frontend-dev:
>cd $(ROOT)/frontend && npm run dev

foundry-bootstrap:
>./scripts/foundry/bootstrap_azd_env.sh

foundry-iac-build:
>az bicep build --file infra/foundry-hosted/iac/main.bicep

foundry-provision:
>./scripts/foundry/ensure_foundry_azd_defaults.sh
>$(MAKE) foundry-iac-build
>cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt

foundry-postgres-rebuild:
>./scripts/foundry/rebuild_postgres_server.sh "$(CONFIRM)"

foundry-postgres-schema:
>bash ./scripts/foundry/bootstrap_postgres_schema.sh

foundry-postgres-credentials:
>./scripts/foundry/provision_postgres_runtime_credentials.sh

foundry-postgres-readiness:
>./scripts/foundry/check_public_postgres_readiness.sh

foundry-backend-deploy: foundry-postgres-readiness
>$(MAKE) foundry-backend-deploy-ready

foundry-backend-deploy-ready:
>./scripts/foundry/deploy_public_backend.sh

foundry-frontend-deploy:
>./scripts/foundry/deploy_public_frontend.sh

foundry-app-deploy:
>$(MAKE) foundry-postgres-readiness
>$(MAKE) -j2 foundry-backend-deploy-ready foundry-frontend-deploy

foundry-deploy: foundry-postgres-readiness
>$(MAKE) foundry-deploy-ready

foundry-deploy-ready:
>./scripts/foundry/deploy_hosted_container.sh

foundry-release-deploy:
>$(MAKE) foundry-postgres-readiness
>$(MAKE) -j3 foundry-backend-deploy-ready foundry-frontend-deploy foundry-deploy-ready

foundry-up:
>$(MAKE) foundry-provision
>$(MAKE) foundry-release-deploy
>$(MAKE) foundry-appinsights-connection

foundry-smoke:
>$(FOUNDRY_RUNTIME_SMOKE) --mode "$(SMOKE_MODE)"

foundry-hosted-e2e:
>./scripts/foundry/hosted_e2e.sh

foundry-eval:
>AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/run_foundry_trace_eval.sh

foundry-appinsights-connection:
>./scripts/foundry/verify_project_appinsights_connection.sh

foundry-telemetry:
>./scripts/foundry/verify_telemetry.sh

foundry-release:
>AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/deploy_public_dev.sh
