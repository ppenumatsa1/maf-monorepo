SHELL := /bin/bash
ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
VENV := $(ROOT).venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
ENV_FILE := $(ROOT).env

ifneq ("$(wildcard $(ENV_FILE))","")
include $(ENV_FILE)
export
endif

.PHONY: help up down logs db-reset install run run-fail-once run-crash resume state events checkpoints \
	test test-local test-backend test-frontend test-e2e \
	lint lint-backend lint-frontend format format-check quality \
	backend-dev frontend-install frontend-dev \
	foundry-bootstrap foundry-iac-build foundry-provision foundry-postgres-rebuild foundry-postgres-schema foundry-postgres-credentials foundry-postgres-readiness foundry-deploy foundry-backend-deploy foundry-frontend-deploy foundry-smoke foundry-eval foundry-native-eval foundry-trace-eval
CRASH_TARGET ?= medical_check

help:
	@printf "Primary local commands:\n"
	@printf "  make up             - Start local postgres, backend, and frontend\n"
	@printf "  make down           - Stop local containers\n"
	@printf "  make logs           - Tail frontend/backend/postgres logs\n"
	@printf "  make install        - Create .venv and install dependencies\n"
	@printf "  make db-reset       - Reset local database schema\n"
	@printf "  make run            - Run happy-path underwriting workflow\n"
	@printf "  make run-fail-once  - Run with one retryable failure injected\n"
	@printf "  make run-crash      - Crash after CRASH_TARGET (default: medical_check)\n"
	@printf "  make resume         - Resume workflow (RUN_ID required)\n"
	@printf "  make state          - Show persisted workflow state (RUN_ID required)\n"
	@printf "  make events         - Show workflow events (RUN_ID required)\n"
	@printf "  make checkpoints    - Show MAF checkpoints (RUN_ID required)\n"
	@printf "  make lint           - Run backend + frontend lint checks\n"
	@printf "  make format         - Format backend code\n"
	@printf "  make quality        - Run lint + format-check + test-local\n"
	@printf "  make test-local     - Run isolated backend + frontend tests\n"
	@printf "  make test           - Alias for test-local\n"
	@printf "  make test-e2e       - Run Playwright end-to-end tests\n"
	@printf "  make foundry-bootstrap - Configure the local azd environment from existing Azure resources\n"
	@printf "  make foundry-iac-build - Compile resource-reuse Foundry Bicep\n"
	@printf "  make foundry-provision - Apply approved PostgreSQL authentication and firewall IaC\n"
	@printf "  make foundry-postgres-rebuild CONFIRM=REBUILD-azpgwhcedyxchnbtmpub - Delete and recreate the fixed PostgreSQL server\n"
	@printf "  make foundry-postgres-schema - Create or migrate the PostgreSQL schema with the administrator credential\n"
	@printf "  make foundry-postgres-credentials - Provision or rotate the local-only PostgreSQL runtime credential\n"
	@printf "  make foundry-postgres-readiness - Verify PostgreSQL TLS, authentication, firewall, and local credential settings\n"
	@printf "  make foundry-deploy  - Build and deploy the hosted underwriting agent\n"
	@printf "  make foundry-backend-deploy - Build and deploy the public backend telemetry change\n"
	@printf "  make foundry-frontend-deploy - Build and deploy the public operations console\n"
	@printf "  make foundry-smoke   - Invoke the deployed Responses agent\n"
	@printf "  make foundry-eval    - Run the report-only Foundry trace evaluation release gate\n"
	@printf "  make foundry-trace-eval - Alias for the report-only Foundry trace evaluation\n"
	@printf "  make foundry-native-eval - Attempt native azd suite generation (policy-blocked diagnostic)\n"

up:
	cd $(ROOT) && docker compose up -d --build postgres backend frontend

down:
	cd $(ROOT) && docker compose down

logs:
	cd $(ROOT) && docker compose logs -f frontend backend postgres

backend-dev:
	cd $(ROOT) && PYTHONPATH=$(ROOT)/backend $(VENV)/bin/uvicorn app.server:app --host 0.0.0.0 --port 8000

install:
	cd $(ROOT) && python3 -m venv .venv
	cd $(ROOT) && $(PIP) install --upgrade pip setuptools wheel
	cd $(ROOT) && $(PIP) install -e ".[dev]"
	cd $(ROOT) && $(PY) -c "import agent_framework; print('agent_framework import OK')"

db-reset:
	cd $(ROOT) && $(PY) -m app.main db-reset

run:
	cd $(ROOT) && $(PY) -m app.main run

run-fail-once:
	cd $(ROOT) && FAIL_RISK_ONCE=true $(PY) -m app.main run

run-crash:
	cd $(ROOT) && CRASH_AFTER_EXECUTOR=$(CRASH_TARGET) $(PY) -m app.main run

resume:
	cd $(ROOT) && $(PY) -m app.main resume --run-id "$(RUN_ID)"

state:
	cd $(ROOT) && $(PY) -m app.main state --run-id "$(RUN_ID)"

events:
	cd $(ROOT) && $(PY) -m app.main events --run-id "$(RUN_ID)"

checkpoints:
	cd $(ROOT) && $(PY) -m app.main checkpoints --run-id "$(RUN_ID)"

test:
	cd $(ROOT) && $(MAKE) test-backend
	cd $(ROOT) && $(MAKE) test-frontend

test-local: test

test-backend:
	@set -euo pipefail; \
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

frontend-install:
	cd $(ROOT)/frontend && npm install

frontend-dev:
	cd $(ROOT)/frontend && npm run dev

test-frontend:
	cd $(ROOT)/frontend && npm run test

test-e2e:
	@set -euo pipefail; \
		postgres_port="$${E2E_POSTGRES_HOST_PORT:-5434}"; \
		backend_port="$${E2E_BACKEND_HOST_PORT:-8000}"; \
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
			PYTHONPATH="$(ROOT)/backend" "$(VENV)/bin/uvicorn" app.server:app --host 127.0.0.1 --port "$$backend_port" > /tmp/underwriting-e2e-backend.log 2>&1 & \
		backend_pid="$$!"; \
		until curl -fsS "http://127.0.0.1:$$backend_port/health" >/dev/null; do sleep 1; done; \
		cd $(ROOT)/frontend && VITE_API_BASE_URL="http://127.0.0.1:$$backend_port" npm run test:e2e

lint:
	cd $(ROOT) && $(MAKE) lint-backend
	cd $(ROOT) && $(MAKE) lint-frontend

lint-backend:
	cd $(ROOT) && $(VENV)/bin/ruff check backend

lint-frontend:
	cd $(ROOT)/frontend && npm run lint

format:
	cd $(ROOT) && $(VENV)/bin/ruff format backend

format-check:
	cd $(ROOT) && $(VENV)/bin/ruff format --check backend

quality:
	cd $(ROOT) && $(MAKE) lint
	cd $(ROOT) && $(MAKE) format-check
	cd $(ROOT) && $(MAKE) test-local

foundry-bootstrap:
	./scripts/foundry/bootstrap_azd_env.sh

foundry-iac-build:
	az bicep build --file infra/foundry-hosted/iac/main.bicep

foundry-provision: foundry-bootstrap foundry-iac-build
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt

foundry-postgres-rebuild:
	./scripts/foundry/rebuild_postgres_server.sh "$(CONFIRM)"

foundry-postgres-schema:
	bash ./scripts/foundry/bootstrap_postgres_schema.sh

foundry-postgres-credentials:
	./scripts/foundry/provision_postgres_runtime_credentials.sh

foundry-postgres-readiness:
	./scripts/foundry/check_public_postgres_readiness.sh

foundry-deploy: foundry-postgres-readiness
	./scripts/foundry/deploy_hosted_container.sh

foundry-backend-deploy:
	./scripts/foundry/deploy_public_backend.sh

foundry-frontend-deploy:
	./scripts/foundry/deploy_public_frontend.sh

foundry-smoke:
	@set -euo pipefail; \
		project_endpoint="$$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AZURE_AI_PROJECT_ENDPOINT --cwd infra/foundry-hosted --no-prompt)"; \
		agent_version="$$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value AGENT_UNDERWRITING_HOSTED_VERSION --cwd infra/foundry-hosted --no-prompt)"; \
		run_id="run-hosted-smoke-$$(date -u +%Y%m%d%H%M%S)"; \
		application_id="app-hosted-smoke-$$(date -u +%Y%m%d%H%M%S)"; \
		payload="{\"protocol\":\"underwriting-hosted-workflow/v1\",\"workflow_run_id\":\"$$run_id\",\"action\":\"start\",\"application\":{\"application_id\":\"$$application_id\",\"applicant_name\":\"Ada Lovelace\",\"age\":38,\"income\":145000,\"requested_coverage\":500000,\"health_disclosures\":\"none\",\"driving_history\":\"clean\",\"credit_score\":760},\"options\":{\"fail_risk_once\":false,\"fail_credit_randomly\":false,\"crash_after_executor\":null}}"; \
		echo "HOSTED_SMOKE_RUN_ID=$$run_id"; \
		AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke \
			--agent-endpoint "$${project_endpoint}/agents/underwriting-hosted/endpoint/protocols/openai/responses?api-version=v1" \
			--version "$$agent_version" "$$payload" \
			--new-conversation --new-session --no-prompt

foundry-eval: foundry-trace-eval

foundry-native-eval:
	cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent eval run --no-prompt

foundry-trace-eval:
	AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/run_foundry_trace_eval.sh
