# Underwriting Operations Console

## Purpose

React/Vite frontend for starting synthetic underwriting scenarios, observing
durable workflow progress, inspecting history/checkpoints, and using the safe
selected-run assistant.

In production, Nginx serves the static application and proxies same-origin
`/api` and `/backend-health` requests to the internal FastAPI Container App.
The browser never receives Foundry, PostgreSQL, Bot, or Teams publication
credentials.

## Install and run

From the project root:

```bash
make frontend-install
make frontend-dev
```

Or run the full containerized stack:

```bash
make up
```

The containerized frontend is available at `http://localhost:4173`.

## Dependency and compiler baseline

- Install with `npm ci`; the lockfile is generated through the Microsoft npm
  proxy configured in `.npmrc`.
- CopilotKit 1.79, React 19.3, Zod 4.6, Vite 8.3, Playwright 1.64, and ESLint
  10.12 are the direct baseline.
- `@typescript/native` provides the TypeScript 7 `tsc` executable used by
  `npm run typecheck` and `npm run build`.
- The `typescript` dependency aliases `@typescript/typescript6` because
  `typescript-eslint` still requires the TypeScript 6 compiler API. Keep the
  alias until the parser supports the TypeScript 7 API.
- Zod remains a CopilotKit peer dependency; this frontend does not import Zod
  directly.
- The musl Rolldown binding is optional and may be skipped on incompatible
  development hosts.

## Validation

```bash
make test-frontend
make lint-frontend
make test-e2e
```

From this directory, the underlying scripts are:

```bash
npm run build
npm run lint
npm run test:e2e
```

Set `PLAYWRIGHT_BASE_URL=<frontend-origin>` only for an explicitly selected
deployed environment.

## Data boundaries

The console may display workflow data required by the operator-facing
underwriting experience. The CopilotKit selected-run assistant is narrower and
may receive only:

- selected run ID;
- normalized status;
- safe event/executor metadata;
- checkpoint summary;
- categorical machine recommendation;
- categorical reviewer outcome.

It must not receive applicant fields, raw checks, score details, prompts,
rationale, model output, checkpoint payloads, Adaptive Card token material,
database values, endpoints, credentials, or secrets.

AG-UI and CopilotKit are additive. Durable run/state/events/checkpoints APIs
remain the refresh and replay authority.

## HITL display rule

Show machine recommendation and reviewer outcome as separate values. Do not
replace `REFER_TO_HUMAN_UNDERWRITER` with `APPROVED` or `DECLINED` after a
review.

Teams Adaptive Card approval is a hosted Activity surface, not a browser
frontend feature. The frontend must not accept or forward Teams action tokens.

## Source authority

- Dependency versions: `package.json` and lockfile.
- Browser acceptance: `tests/e2e/`.
- API/telemetry schema: [schema, I/O, and telemetry](../docs/design/schema-io-telemetry.md).
- Product behavior: [functional specification](../docs/design/functional-spec.md).
