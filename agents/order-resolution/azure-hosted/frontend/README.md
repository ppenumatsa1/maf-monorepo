# Frontend - React + Vite

```bash
cd frontend
npm install
npm run dev
```

The app defaults to backend `http://localhost:8000` during Vite development.
Containers default browser requests to same-origin `/api`; Nginx renders that
proxy from `NGINX_API_UPSTREAM`. Docker Compose points it to
`http://backend:8000`, while Azure points it to the deployed backend HTTPS URL.
`API_BASE` (or `VITE_API_BASE_URL` / `VITE_API_BASE`) may override the base for
an isolated deployment.

Optional selected-thread integrations can be configured at runtime with
`AG_UI_URL` and `COPILOTKIT_URL`, or at build time with `VITE_AG_UI_URL` and
`VITE_COPILOTKIT_URL`. When unset they use same-origin
`/api/chat/stream/{threadId}/ag-ui` and `/api/copilotkit`. They are read-only:
the native SSE timeline and HITL controls remain the source of truth.

Runtime configuration injected in `env-config.js` wins over Vite values:
`API_BASE`, `AG_UI_URL`, and `COPILOTKIT_URL` are read from
`window.__APP_CONFIG__`. This permits one browser bundle to be configured for
the deployed frontend proxy without rebuilding it.

Workflow Studio runtime info:

- Runtime badge reads backend `/health` metadata to display active environment/mode.
- In deployed frontend containers the badge uses proxied `/api/health` first so
  it does not read the frontend container's own `/health` endpoint.

UI highlights:

- Workflow history uses paginated API calls (`/api/workflows?page=<n>&page_size=<n>`).
- Event timeline uses rich SSE (`/api/chat/stream/{thread_id}/rich`) for live updates, while polling details remains as fallback.
- Right panel includes a RAG Evidence view that surfaces retrieved policy evidence and chunk IDs from workflow events/details when available.
- AG-UI and CopilotKit panels are optional read-only selected-thread views.
  CopilotKit receives only allowlisted thread metadata, never raw native rich
  events or workflow payloads, and its inspector is disabled.

CopilotKit (`@copilotkit/react-core`) is not the GitHub Copilot SDK. Its POST
bridge only selects an existing durable thread; it cannot perform a chat,
approval, resume, or other workflow mutation.
