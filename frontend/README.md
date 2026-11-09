# Sentra-X: Frontend Workspace

**Reactive Single-Page Application (SPA) built with React 19, TypeScript, Vite, and Tailwind CSS**

---

## 1. Overview

The `frontend/` package provides the complete SOC analyst workstation user interface for **Sentra-X**:
- **Modern React 19 Architecture:** Built with native functional components, reactive hooks (`useContext`, `useMemo`, `useState`, `useEffect`), and concurrent state transitions. Zero legacy class components.
- **Strict TypeScript Typing:** Complete type safety matching PostgreSQL models and Pydantic schemas 1:1 (`src/types/sentrax.ts`) with zero implicit `any`.
- **Hybrid Data Boundary:** Connects to the FastAPI backend gateway (`localhost:8000/api/v1`) via Axios with JWT Bearer authentication. If the backend is unreachable, the services layer (`src/api/services.ts`) automatically falls back to an isolated in-memory reactive store (`src/mock/demoData.ts`) for demonstration resilience.
- **SOC Workspace Design Language:** Styled with Tailwind CSS 4 using a professional dark palette (pure `#000000` canvas, `zinc-950` cards, `zinc-800` borders, and high-visibility status indicators).

---

## 2. Directory Structure

```
frontend/
├── public/                      # Static assets served at root
│   ├── favicon.svg              # Sentra-X application icon
│   └── icons.svg                # Vector SVG sprite definitions
├── src/
│   ├── api/                     # Backend communication layer
│   │   ├── client.ts            # Axios instance with request/response JWT interceptors
│   │   └── services.ts          # Typed REST service layer with transparent fallback store
│   ├── components/              # Modular UI components
│   │   ├── analytics/           # KPI grids, override trend charts, severity delta matrices
│   │   ├── badges/              # Severity, verdict, confidence, asset tier, guardrail badges
│   │   ├── evaluation/          # Adversarial suite tables, comparative scorecard, user admin
│   │   ├── governance/          # Few-shot exemplar table, monitored asset registry
│   │   ├── layout/              # AppShell header, sidebar navigation, ProtectedRoute guard
│   │   ├── modal/               # Split-pane alert detail modal, evidence tree, decision panel
│   │   ├── queue/               # Prioritized triage queue table, multi-parameter filter bar
│   │   └── ui/                  # Reusable primitives (button, card, dialog, dropdown-menu)
│   ├── context/
│   │   └── AuthContext.tsx      # JWT session management and evaluator demo role switcher
│   ├── lib/
│   │   └── utils.ts             # Tailwind class merging utility (clsx + tailwind-merge)
│   ├── mock/
│   │   └── demoData.ts          # Authentic Wazuh SOC baseline dataset for offline fallback
│   ├── types/
│   │   └── sentrax.ts           # Unified TypeScript domain definitions matching SRS v1.4
│   ├── views/                   # Full-page route views
│   │   ├── TriageQueueView.tsx         # /queue (Live alert prioritization & quick approval)
│   │   ├── TeamLeadAnalyticsView.tsx   # /analytics (Supervisor agreement KPIs & CSV export)
│   │   ├── GovernanceView.tsx          # /governance (Exemplar revocation & asset registry)
│   │   ├── EvaluationRunnerView.tsx    # /admin/evaluation (Adversarial benchmark runner)
│   │   └── LoginView.tsx               # /login (Role-based authentication & demo switcher)
│   ├── App.tsx                  # Root application component and React Router v7 routes
│   ├── main.tsx                 # React 19 DOM mount entry point
│   └── index.css                # Global CSS styles and Tailwind imports
├── package.json                 # Pinned dependencies and execution scripts
├── tsconfig.json                # TypeScript compiler configuration
└── vite.config.ts               # Vite build configuration
```

---

## 3. Quick Start

### Prerequisites
- Node.js `v20.x` or higher
- npm `v10.x` or higher

### Installation & Development
```bash
# 1. Install dependencies:
npm install

# 2. Start local development server with Hot Module Replacement:
npm run dev
```
The application will launch at `http://localhost:5173/`.

### Production Build & Type-Checking
```bash
# Type-check TypeScript and bundle production assets:
npm run build

# Preview the production build locally:
npm run preview
```

---

## 4. Evaluator Demo Role Switcher

The login view (`/login`) includes one-click demo role switchers to simulate all three Role-Based Access Control personas without manual credential entry:

| Persona | Role | Default Username | Scope & Permissions |
| :--- | :---: | :--- | :--- |
| **SOC Analyst** | `Analyst` | `analyst_01` | Access triage queue, inspect evidence packs, 2-click quick approve, submit overrides with mandatory rationale ($\ge 10$ chars), escalate alerts. |
| **SOC Team Lead** | `TeamLead` | `teamlead_mercer` | All Analyst permissions + access Agreement Analytics, streaming CSV audit export, revoke few-shot exemplars, edit host criticality tiers. |
| **Super Admin** | `Admin` | `admin_sys` | Full access + execute Adversarial Benchmark runner, modify system configuration parameters, manage users. |

---

## 5. Environment Variables

Create a `.env` file in `frontend/` to customize the backend API endpoint:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```
If omitted, the application defaults to `http://localhost:8000/api/v1`.
