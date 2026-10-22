# Frontend - React + Vite

## Run locally

```bash
cd frontend
npm ci
npm run dev
```

The Vite app defaults to `http://localhost:8000` for local API calls.

## Frontend toolchain

- Runtime: React/React DOM 19.3, CopilotKit 1.79, and Zod 4.6.
- Build/test: Vite 8.3, Playwright 1.64, ESLint 10.12, TypeScript ESLint
  8.71, and the React plugin 6.1 line.
- `@typescript/native` supplies the TypeScript 7 `tsc` executable used by
  `npm run typecheck` and `npm run build`.
- The `typescript` dependency aliases `@typescript/typescript6` because
  `typescript-eslint` still requires the TypeScript 6 compiler API.
- Installation uses the Microsoft npm proxy configured in `.npmrc`.

The exact baseline is captured in `package.json` and `package-lock.json`.

## Deployed topology

The frontend Container App is the only browser-facing service. Nginx proxies
same-origin `/api` to the internal FastAPI backend through
the required `NGINX_API_UPSTREAM`. The browser must not receive the internal
backend URL, database settings, or Foundry credentials.

Docker Compose points the proxy to `http://backend:8000`. Azure injects the
profile-selected internal backend upstream at deployment time.

## Runtime configuration

`env-config.js` values take precedence over Vite build-time values:

- `API_BASE`
- `AG_UI_URL`
- `COPILOTKIT_URL`

When optional selected-thread URLs are unset, the application uses
same-origin `/api/chat/stream/{threadId}/ag-ui` and `/api/copilotkit`.

## UI contracts

- Native SSE and durable workflow history are authoritative.
- The rich stream is a native-payload contract and must not be passed into an
  assistant UI.
- AG-UI and CopilotKit are read-only selected-thread views.
- CopilotKit means `@copilotkit/react-core`, not the GitHub Copilot SDK.
- The CopilotKit inspector remains disabled.
- Optional selected-thread failures must not block native history, timeline,
  or HITL controls.

## Build constraints

The release image retains Node 20 Alpine and Nginx Alpine. The package graph
includes the Rolldown Linux x64 musl binding, and the Docker build retries the
approved-feed install while verifying that the TypeScript 7 `tsc` executable
was installed before building.

See the [user flow](../docs/userflow.md) and
[technical specification](../docs/technical-spec.md).
