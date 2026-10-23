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
FOUNDRY_DEPLOYMENT_PROFILE ?= $(ROOT)deployment/profiles/foundry-public.env
TEAMS_PUBLISH_SCOPE ?= Shared
TEAMS_PUBLICATION_MANIFEST ?= infra/foundry-hosted/teams-publication.json
TEAMS_PUBLICATION_ARGS ?=

ifneq ("$(wildcard $(ENV_FILE))","")
include $(ENV_FILE)
export
endif

.PHONY: help bootstrap up down logs db-reset install frontend-install foundry-python-wheelhouse run run-fail-once run-crash resume state events checkpoints \
	backend-dev frontend-dev \
	test test-backend test-frontend test-scripts test-deployment-profile test-capacity-preflight test-preview-safety test-foundry-activity-endpoint test-foundry-teams-publishing test-public-portability test-e2e \
	lint lint-backend lint-frontend format format-check quality validate-quick validate-full \
	foundry-profile-apply foundry-bootstrap foundry-bootstrap-env foundry-iac-build foundry-provision foundry-provision-infrastructure foundry-provision-converge foundry-postgres-rebuild foundry-postgres-schema \
	foundry-postgres-credentials foundry-postgres-readiness foundry-backend-deploy foundry-frontend-deploy \
	foundry-release-readiness foundry-model-preflight foundry-capacity-preflight-full foundry-provision-preview foundry-reuse-preview foundry-runtime-connection foundry-rbac foundry-package \
	foundry-release-package foundry-release-build foundry-release-hosted-activate foundry-release-app-deploy \
	foundry-backend-deploy-ready foundry-frontend-deploy-ready foundry-deploy-ready foundry-app-deploy foundry-release-deploy foundry-deploy \
	foundry-backend-internalize foundry-release-rollback-baseline foundry-rollback-verify foundry-verify foundry-evidence \
	foundry-up foundry-smoke foundry-hosted-e2e foundry-eval \
	foundry-appinsights-connection foundry-telemetry foundry-release \
	foundry-activity-plan foundry-activity-apply foundry-activity-rollback \
	foundry-teams-plan foundry-teams-preview foundry-teams-deploy-bot foundry-teams-package foundry-teams-publish foundry-teams-status foundry-teams-rollback-plan foundry-teams-rollback

CRASH_TARGET ?= medical_check
SMOKE_MODE ?= happy

help:
>@printf "Primary local commands:\n"
>@printf "  make bootstrap                    - Install Python and frontend dependencies\n"
>@printf "  make up                           - Start local postgres, backend, and frontend\n"
>@printf "  make down                         - Stop local containers\n"
>@printf "  make logs                         - Tail frontend/backend/postgres logs\n"
>@printf "  make install                      - Create .venv and install Python dependencies\n"
>@printf "  make frontend-install             - Install locked frontend dependencies\n"
>@printf "  make foundry-python-wheelhouse    - Prepare hash-verified CPython 3.13 Linux AMD64 wheels\n"
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
>@printf "  make test-deployment-profile      - Run non-secret target-profile contract checks\n"
>@printf "  make test-e2e                     - Run Playwright end-to-end tests\n"
>@printf "\nFoundry public release commands:\n"
>@printf "  make foundry-profile-apply FOUNDRY_DEPLOYMENT_PROFILE=/secure/path/profile.env\n"
>@printf "                                     - Select an existing non-secret target profile\n"
>@printf "  make foundry-bootstrap            - Refresh the local azd environment from the reused Azure resources\n"
>@printf "  make foundry-bootstrap-env        - Populate a new environment's non-secret bootstrap parameters\n"
>@printf "  make foundry-iac-build            - Compile bootstrap/reuse Foundry Bicep\n"
>@printf "  make foundry-package              - Package backend, frontend, and hosted services with AZD\n"
>@printf "  make foundry-provision            - Apply infrastructure, migrate schema, converge runtime access, and verify readiness\n"
>@printf "  make foundry-provision-infrastructure - Apply approved Bicep and hydrate existing-resource outputs\n"
>@printf "  make foundry-provision-converge   - Migrate schema, converge runtime credential/connection, and verify readiness\n"
>@printf "  make foundry-postgres-rebuild CONFIRM=REBUILD-<selected-postgres-server>\n"
>@printf "                                     Delete and recreate the selected AZD PostgreSQL server\n"
>@printf "  make foundry-postgres-schema      - Create or migrate the PostgreSQL schema with the administrator credential\n"
>@printf "  make foundry-postgres-credentials - Provision or rotate the local-only PostgreSQL runtime credential\n"
>@printf "  make foundry-runtime-connection   - Converge the project CustomKeys connection for the runtime URL\n"
>@printf "  make foundry-postgres-readiness   - Verify PostgreSQL TLS, auth, firewall, and runtime credential readiness\n"
>@printf "  make foundry-model-preflight      - Verify configured model deployment, SKU, capacity, and regional quota\n"
>@printf "  make foundry-capacity-preflight-full - Check only incremental North America infrastructure capacity\n"
>@printf "  make foundry-reuse-preview        - Require a zero-change public reuse preview\n"
>@printf "  make foundry-provision-preview    - Preview create-only full infrastructure changes\n"
>@printf "  make foundry-release-readiness    - Run the single shared database/model readiness gate\n"
>@printf "  make foundry-backend-deploy       - Build and deploy the internal backend adapter\n"
>@printf "  make foundry-frontend-deploy      - Build and deploy the public operations console\n"
>@printf "  make foundry-backend-internalize CONFIRM=INTERNALIZE-<backend-name>\n"
>@printf "                                     - One-time, fail-closed public-to-internal backend migration\n"
>@printf "  make foundry-app-deploy           - Verify shared readiness, then deploy public apps concurrently\n"
>@printf "  make foundry-deploy               - Build and deploy the hosted underwriting agent\n"
>@printf "  make foundry-release-deploy       - Readiness/package, hosted metadata, then parallel backend/frontend deploy\n"
>@printf "  make foundry-up                   - Provision, deploy all release components concurrently, and verify App Insights connection\n"
>@printf "  make foundry-smoke                - Run direct hosted-agent smoke and write trace-eval evidence\n"
>@printf "  make foundry-hosted-e2e           - Run hosted API smoke plus deployed Playwright E2E\n"
>@printf "  make foundry-eval                 - Run the report-only Foundry trace evaluation gate\n"
>@printf "  make foundry-appinsights-connection - Verify the Foundry project App Insights connection\n"
>@printf "  make foundry-telemetry            - Verify App Insights evidence for hosted E2E run IDs\n"
>@printf "  make foundry-verify               - Verify deployed topology, images, hosted agent, telemetry connection, and DB mode\n"
>@printf "  make foundry-rollback-verify      - Verify the prior hosted version and ACA revisions remain rollback-ready\n"
>@printf "  make foundry-evidence             - Aggregate secret-free release-window evidence\n"
>@printf "  make foundry-activity-{plan,apply,rollback} - Merge-preserving Activity endpoint lifecycle\n"
>@printf "  make foundry-teams-{plan,preview,deploy-bot,package,publish,status,rollback} - Shared Microsoft 365 publication lifecycle\n"
>@printf "  make foundry-release RELEASE_ID=<id> - Route validation/deployment and run the public release sequence\n"

bootstrap: install frontend-install

up: foundry-python-wheelhouse
>cd $(ROOT) && docker compose up -d --build postgres backend frontend

down:
>cd $(ROOT) && docker compose down

logs:
>cd $(ROOT) && docker compose logs -f frontend backend postgres

backend-dev:
>cd $(ROOT) && PYTHONPATH=$(ROOT)/backend $(VENV)/bin/uvicorn app.server:app --host 0.0.0.0 --port 8000

install:
>@if [[ ! -x "$(PY)" ]] || [[ "$$($(PY) -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)" != "3.13" ]]; then \
		rm -rf "$(VENV)"; \
		python3.13 -m venv "$(VENV)"; \
	fi
>cd $(ROOT) && $(PIP) install --require-hashes -r backend/requirements-dev.lock
>cd $(ROOT) && $(PIP) install --no-build-isolation --no-deps -e .
>cd $(ROOT) && $(PY) -c "import agent_framework; print('agent_framework import OK')"

frontend-install:
>cd $(ROOT)/frontend && npm ci

foundry-python-wheelhouse:
>cd $(ROOT) && ./scripts/foundry/build_python_wheelhouse.sh

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
>cd $(ROOT) && PYTHONPATH="$(ROOT)/backend" "$(PYTEST)" scripts/foundry/tests/test_hosted_runtime_secret_contract.py scripts/foundry/tests/test_hosted_deployment_contract.py scripts/foundry/tests/test_hosted_review_e2e.py scripts/foundry/tests/test_aggregate_release_evidence.py scripts/foundry/tests/test_release_authority.py
>cd $(ROOT) && bash scripts/foundry/tests/test_runtime_secret_connection_contract.sh
>cd $(ROOT) && bash scripts/foundry/tests/test_bootstrap_infrastructure_contract.sh
>cd $(ROOT) && bash scripts/foundry/tests/test_bootstrap_hydration_contract.sh
>cd $(ROOT) && bash scripts/foundry/tests/test_release_scripts_contract.sh
>cd $(ROOT) && $(MAKE) test-capacity-preflight test-preview-safety test-foundry-activity-endpoint test-foundry-teams-publishing test-public-portability

test-deployment-profile:
>cd $(ROOT) && bash deployment/tests/test-profile.sh

test-capacity-preflight:
>cd $(ROOT) && python3 -m unittest discover -s scripts/foundry/tests -p 'test_capacity_preflight.py'

test-preview-safety:
>cd $(ROOT) && python3 -m unittest discover -s scripts/foundry/tests -p 'test_preview_safety.py'

test-foundry-activity-endpoint:
>cd $(ROOT) && python3 -m unittest discover -s scripts/foundry/tests -p 'test_activity_endpoint_reconciler.py'

test-foundry-teams-publishing:
>cd $(ROOT) && python3 -m unittest discover -s scripts/foundry/tests -p 'test_teams_publishing.py'
>cd $(ROOT) && python3 -m unittest discover -s infra/foundry-hosted/iac/teams/tests -p 'test_teams_iac_contract.py'

test-public-portability:
>cd $(ROOT) && bash scripts/foundry/tests/test_public_portability_contract.sh

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

foundry-bootstrap-env:
>./scripts/foundry/prepare_bootstrap_env.sh

foundry-profile-apply:
>bash ./deployment/apply-azd-profile.sh "$(FOUNDRY_DEPLOYMENT_PROFILE)"

foundry-iac-build:
>az bicep build --file infra/foundry-hosted/iac/main.bicep
>az bicep build --file infra/foundry-hosted/iac/teams/main.bicep --stdout >/dev/null

foundry-package: foundry-python-wheelhouse
>./scripts/foundry/sync_hosted_source.sh
>cd infra/foundry-hosted && azd package --no-prompt

foundry-release-package: foundry-python-wheelhouse
>./scripts/foundry/sync_hosted_source.sh
>test -f backend/Dockerfile
>test -f frontend/Dockerfile
>test -f infra/foundry-hosted/agent/Dockerfile
>test -f infra/foundry-hosted/agent/backend/foundry/main.py

foundry-release-build: foundry-python-wheelhouse
>./scripts/foundry/build_release_images.sh

foundry-release-hosted-activate:
>@set -euo pipefail; \
>source "$${FOUNDRY_RELEASE_EVIDENCE_DIR}/release-images.env"; \
>export HOSTED_AGENT_PREBUILT_IMAGE; \
>./scripts/foundry/deploy_hosted_container.sh

foundry-release-app-deploy:
>@set -euo pipefail; \
>source "$${FOUNDRY_RELEASE_EVIDENCE_DIR}/release-images.env"; \
>export PUBLIC_BACKEND_PREBUILT_IMAGE PUBLIC_FRONTEND_PREBUILT_IMAGE; \
>./scripts/foundry/deploy_public_backend.sh & backend_pid=$$!; \
>./scripts/foundry/deploy_public_frontend.sh & frontend_pid=$$!; \
>status=0; \
>wait "$$backend_pid" || status=1; \
>wait "$$frontend_pid" || status=1; \
>(( status == 0 )) || exit 1; \
>./scripts/foundry/verify_project_appinsights_connection.sh

foundry-release-rollback-baseline:
>./scripts/foundry/capture_release_rollback_baseline.sh

foundry-provision: foundry-provision-infrastructure foundry-provision-converge

foundry-provision-infrastructure:
>@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "Set FOUNDRY_FULL_INFRA_AUTHORIZED=true after reviewing the full infrastructure preview." >&2; exit 2; }
>@set -euo pipefail; \
	mode="$$(azd env get-value INFRASTRUCTURE_MODE --cwd infra/foundry-hosted --no-prompt)"; \
	case "$$mode" in \
		bootstrap) ./scripts/foundry/prepare_bootstrap_env.sh ;; \
		reuse) ./scripts/foundry/bootstrap_azd_env.sh; ./scripts/foundry/ensure_foundry_azd_defaults.sh ;; \
		*) echo "INFRASTRUCTURE_MODE must be bootstrap or reuse." >&2; exit 1 ;; \
	esac
>$(MAKE) foundry-iac-build
>@set -euo pipefail; \
	mode="$$(azd env get-value INFRASTRUCTURE_MODE --cwd infra/foundry-hosted --no-prompt)"; \
	case "$$mode" in \
		reuse) FOUNDRY_CAPACITY_MODE=full_infra ./scripts/foundry/preflight_foundry_model.sh ;; \
		bootstrap) echo "Bootstrap mode retained; existing-resource capacity inventory is deferred until resources exist." ;; \
		*) echo "INFRASTRUCTURE_MODE must be bootstrap or reuse." >&2; exit 1 ;; \
	esac
>cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt
>FOUNDRY_BOOTSTRAP_HYDRATE=1 ./scripts/foundry/bootstrap_azd_env.sh

foundry-provision-converge:
>$(MAKE) foundry-postgres-credentials
>$(MAKE) foundry-postgres-readiness

foundry-postgres-rebuild:
>./scripts/foundry/rebuild_postgres_server.sh "$(CONFIRM)"

foundry-postgres-schema:
>bash ./scripts/foundry/bootstrap_postgres_schema.sh

foundry-postgres-credentials: foundry-postgres-schema
>./scripts/foundry/provision_postgres_runtime_credentials.sh
>$(MAKE) foundry-runtime-connection

foundry-postgres-readiness:
>./scripts/foundry/check_public_postgres_readiness.sh

foundry-model-preflight:
>./scripts/foundry/preflight_foundry_model.sh

foundry-capacity-preflight-full:
>FOUNDRY_CAPACITY_MODE=full_infra ./scripts/foundry/preflight_foundry_model.sh

foundry-provision-preview:
>FOUNDRY_PREVIEW_MODE=full_infra FOUNDRY_DEPLOYMENT_PROFILE="$(FOUNDRY_DEPLOYMENT_PROFILE)" ./scripts/foundry/preview_public_infrastructure.sh

foundry-reuse-preview:
>FOUNDRY_PREVIEW_MODE=reuse FOUNDRY_DEPLOYMENT_PROFILE="$(FOUNDRY_DEPLOYMENT_PROFILE)" ./scripts/foundry/preview_public_infrastructure.sh

foundry-runtime-connection:
>./scripts/foundry/converge_runtime_secret_connection.sh

foundry-rbac:
>./scripts/foundry/converge_hosted_agent_rbac.sh

foundry-release-readiness:
>$(MAKE) foundry-postgres-readiness
>$(MAKE) foundry-model-preflight
>$(MAKE) foundry-runtime-connection

foundry-backend-deploy: foundry-release-readiness
>$(MAKE) foundry-backend-deploy-ready

foundry-backend-deploy-ready: foundry-python-wheelhouse
>./scripts/foundry/deploy_public_backend.sh

foundry-frontend-deploy: foundry-release-readiness
>$(MAKE) foundry-frontend-deploy-ready

foundry-frontend-deploy-ready:
>./scripts/foundry/deploy_public_frontend.sh

foundry-app-deploy:
>$(MAKE) foundry-release-readiness
>$(MAKE) -j2 foundry-backend-deploy-ready foundry-frontend-deploy-ready

foundry-deploy: foundry-release-readiness
>$(MAKE) foundry-deploy-ready

foundry-deploy-ready: foundry-python-wheelhouse
>./scripts/foundry/deploy_hosted_container.sh

foundry-release-deploy:
>$(MAKE) foundry-release-readiness
>$(MAKE) foundry-release-package
>$(MAKE) foundry-release-build
>$(MAKE) foundry-release-hosted-activate
>$(MAKE) foundry-release-app-deploy

foundry-backend-internalize:
>./scripts/foundry/internalize_backend_ingress.sh "$(CONFIRM)"

foundry-up:
>$(MAKE) foundry-provision
>$(MAKE) foundry-release-deploy
>$(MAKE) foundry-appinsights-connection

foundry-smoke:
>$(FOUNDRY_RUNTIME_SMOKE) --mode "$(SMOKE_MODE)"

foundry-hosted-e2e:
>./scripts/foundry/hosted_e2e.sh

foundry-teams-native-acceptance:
>$(PY) scripts/foundry/hosted_review_e2e.py --observation-started-at "$$(date -u +%Y-%m-%dT%H:%M:%SZ)"

foundry-eval:
>AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/run_foundry_trace_eval.sh

foundry-appinsights-connection:
>./scripts/foundry/verify_project_appinsights_connection.sh

foundry-telemetry:
>./scripts/foundry/verify_telemetry.sh

foundry-verify:
>./scripts/foundry/verify_foundry_release.sh

foundry-rollback-verify:
>./scripts/foundry/verify_release_rollback.sh

foundry-evidence:
>@runtime_database_url="$$(cd infra/foundry-hosted && azd env get-value RUNTIME_DATABASE_URL --no-prompt)"; \
>  test -n "$$runtime_database_url" || { echo "RUNTIME_DATABASE_URL is required for evidence secret validation." >&2; exit 1; }; \
>  DATABASE_URL="$$runtime_database_url" RUNTIME_DATABASE_URL="$$runtime_database_url" \
>  $(PY) ./scripts/foundry/aggregate_release_evidence.py

foundry-activity-plan:
>python3 ./scripts/foundry/reconcile_activity_endpoint.py plan --publish-scope "$(TEAMS_PUBLISH_SCOPE)"

foundry-activity-apply:
>python3 ./scripts/foundry/reconcile_activity_endpoint.py apply --publish-scope "$(TEAMS_PUBLISH_SCOPE)"

foundry-activity-rollback:
>python3 ./scripts/foundry/reconcile_activity_endpoint.py rollback --publish-scope "$(TEAMS_PUBLISH_SCOPE)"

foundry-teams-plan:
>python3 ./scripts/foundry/publish_teams_agent.py plan --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-preview:
>python3 ./scripts/foundry/publish_teams_agent.py preview-bot --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-deploy-bot:
>@test "$${FOUNDRY_FULL_INFRA_AUTHORIZED:-}" = "true" || { echo "Set FOUNDRY_FULL_INFRA_AUTHORIZED=true after reviewing the Teams what-if." >&2; exit 2; }
>python3 ./scripts/foundry/publish_teams_agent.py deploy-bot --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-package:
>python3 ./scripts/foundry/publish_teams_agent.py package --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-publish:
>python3 ./scripts/foundry/publish_teams_agent.py publish --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-status:
>python3 ./scripts/foundry/publish_teams_agent.py status --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-rollback-plan:
>python3 ./scripts/foundry/publish_teams_agent.py rollback-plan --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-teams-rollback:
>python3 ./scripts/foundry/publish_teams_agent.py rollback --manifest "$(TEAMS_PUBLICATION_MANIFEST)" $(TEAMS_PUBLICATION_ARGS)

foundry-release: install frontend-install foundry-python-wheelhouse
>AZURE_DEV_USER_AGENT=microsoft_foundry_skill ./scripts/foundry/deploy_public_dev.sh
