# Frontend - React + Vite

```bash
cd frontend
npm ci
npm run dev
```

## Frontend toolchain

- `@typescript/native` provides the TypeScript 7 `tsc` executable used by
  `npm run typecheck` and `npm run build`.
- The `typescript` dependency aliases `@typescript/typescript6` because
  `typescript-eslint` still requires the TypeScript 6 compiler API. Do not
  replace the alias with TypeScript 7 until `typescript-eslint` supports the
  TypeScript 7 API.
- Zod 4 satisfies CopilotKit's `zod >=3.25` peer dependency. The application
  does not currently import Zod directly.
- Package installation uses the Microsoft npm proxy configured in `.npmrc`.

The app defaults to backend `http://localhost:8000` during Vite development.
The container runtime writes `env-config.js` from `API_BASE` and renders the
Nginx `/api/` proxy from `NGINX_API_UPSTREAM`; Docker Compose points the proxy
to `http://backend:8000`, while Azure points it to the deployed backend HTTPS
URL.

Workflow Studio runtime info:

- Runtime badge reads backend `/health` metadata to display active environment/mode.
- In deployed frontend containers the badge uses proxied `/api/health` first so
  it does not read the frontend container's own `/health` endpoint.

UI highlights:

- Workflow history uses paginated API calls (`/api/workflows?page=<n>&page_size=<n>`).
- Event timeline uses rich SSE (`/api/chat/stream/{thread_id}/rich`) for live updates, while polling details remains as fallback.
- Right panel includes a RAG Evidence view that surfaces retrieved policy evidence and chunk IDs from workflow events/details when available.

Hosted runtime note (2026-07-15):

- Frontend workflow behavior and SSE event contracts are unchanged by the recent Foundry tracing fixes; updates were confined to hosted runtime/deploy surfaces.
