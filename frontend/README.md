# Doc-mate — Frontend

Next.js (App Router) + TypeScript + Tailwind CSS + TanStack Query. The doctor
**Patient Snapshot** is the centerpiece: a fast, calm, citation-backed read of a
patient's longitudinal record. The AI **summarises and cites — it never
diagnoses**.

## Prerequisites

- Node.js 18.18+ (tested on Node 24)
- The FastAPI backend running at `http://localhost:8000` (for live auth/data)

## Setup

```bash
cd frontend
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL if not localhost:8000
npm install
npm run dev                  # http://localhost:3000
```

## Scripts

| Command             | Purpose                          |
| ------------------- | -------------------------------- |
| `npm run dev`       | Start the dev server (port 3000) |
| `npm run build`     | Production build                 |
| `npm run start`     | Serve the production build       |
| `npm run lint`      | ESLint (next/core-web-vitals)    |
| `npm run typecheck` | `tsc --noEmit` (strict)          |

## Environment

| Variable              | Default                 | Notes                     |
| --------------------- | ----------------------- | ------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the backend.  |

## Routes

| Route                          | Role      | Description                                    |
| ------------------------------ | --------- | ---------------------------------------------- |
| `/`                            | public    | Landing + login (routes by role on success)   |
| `/reception/patients`          | reception | Patient list + "New patient" entry point       |
| `/reception/patients/new`      | reception | Create patient + multi-file upload (UI)        |
| `/doctor/patients`             | doctor    | Patient list                                   |
| `/doctor/patients/[id]`        | doctor    | **Patient Snapshot** (the wow screen)          |

## Auth / token flow

1. `POST {API}/auth/login` with `{ email, password }` → `{ access_token, token_type, role }`.
2. The JWT is stored in `localStorage` (fine for the demo) and sent as
   `Authorization: Bearer <token>` on every request.
3. `GET {API}/auth/me` resolves the current user on load and after login.
4. `AuthProvider` (`lib/auth.tsx`) exposes `login`, `logout`, `user`, `role`,
   `status`. `RequireRole` guards each screen and redirects by role.

Roles: `reception` and `doctor`.

## i18n

Lightweight typed dictionaries for **English / Hindi / Tamil** in
`lib/i18n/dictionaries.ts`, switched via `I18nProvider` + the header
`LanguageSwitcher`. The chosen locale is remembered in `localStorage`.

## Notes

- The patient list and snapshot use **synthetic mock data** (`lib/mock-data.ts`)
  so the UI is complete before the backend ingestion/RAG pipeline is wired in.
  The typed API client (`lib/api.ts`) is ready to replace the mocks.
- Citation chips are load-bearing but currently no-op stubs; they will open the
  source document/region once the backend viewer exists.
