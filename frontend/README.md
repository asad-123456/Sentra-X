# Sentra-X frontend

The React SPA provides sign-in, the analyst queue and evidence modal, team-lead analytics, governance, and admin evaluation. The frontend adds navigation gates, while FastAPI governs API access.

## Setup

Use Node.js 22.12+ to match the container's Node 22 line. Vite also supports Node 20.19+ on the Node 20 line. Run from `frontend/`:

```powershell
npm ci
npm run dev
```

Vite serves the app at `http://localhost:5173` by default. `npm run lint` runs ESLint. `npm run build` typechecks and bundles the SPA, and `npm run preview` serves the production build locally.

## Offline mode

Leave `VITE_API_BASE_URL` blank or unset. The browser uses an in-memory demo store with fixture results. Use the demo role controls to explore the workspace. Reloading resets store changes.

## Live mode

Set the backend origin in `frontend/.env` or in the process environment before starting Vite or building:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

Use the origin alone. The services append `/api/v1` to application routes. If a backend request fails, the UI remains in live mode and displays an error. The [Compose lab](../backend/README.md#loopback-compose-lab) builds with `VITE_API_BASE_URL=/`, so the browser sends live API requests to the same origin as the page through Nginx.

Live sign-in uses backend accounts. On reload, the browser checks the saved token with `/api/v1/auth/me` before opening protected pages. Demo role controls are available in offline mode. See [named account setup](../backend/README.md#named-accounts) for a lab without demo seeding.

In the live queue, open an alert and select a citation to expand and highlight its saved evidence field. The action bar reflects the alert state and your role. After a decision, the open dialog refreshes and shows the saved actor and rationale while the queue keeps its filters. If a decision is rejected because the alert changed, use **Refresh alert** to see the latest state.

## Source layout

- [`src/App.tsx`](src/App.tsx) defines routes and role-gated navigation.
- [`src/api/client.ts`](src/api/client.ts) wraps Fetch and sends the saved bearer token. [`services.ts`](src/api/services.ts) switches between live calls and fixtures.
- [`src/types/sentrax.ts`](src/types/sentrax.ts) contains client-facing API types.
- [`src/views/`](src/views/) owns page state. [`src/components/`](src/components/) contains feature components and shared UI primitives. [`src/index.css`](src/index.css) contains global styles.
