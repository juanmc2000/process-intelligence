# UI Current State

Last updated: Sprint 7

This document describes the current implementation state of the frontend UI: which
pages use real API data, which sections are static or placeholder, and what the
known limitations are.

---

## Frontend Stack

- **Framework:** Next.js 14 (App Router, TypeScript)
- **Styling:** Tailwind CSS with CSS custom properties design tokens
- **Graph:** React Flow (reactflow)
- **API client:** `frontend/lib/api.ts` — typed, all requests to `NEXT_PUBLIC_API_URL`
- **Docker port:** 3000

---

## Route Inventory

| Route | Status | Real data? | Notes |
|---|---|---|---|
| `/` | Wired | Partial | Workflow cards from `GET /processes`; activity feed is static demo |
| `/health` | Wired | Yes | Polls `GET /health` |
| `/runs/upload` | Wired | Yes | Posts to `POST /upload`; shows upload result |
| `/runs/[id]` | Wired | Yes | Polls `GET /runs/{id}` until terminal state |
| `/runs/[id]/review` | Wired | Yes | `GET /runs/{id}/review`; review actions via POST endpoints |
| `/processes` | Wired | Yes | `GET /processes` + `GET /processes/groups` |
| `/processes/[id]` | Wired | Yes | `GET /processes/{id}` — Narrative and Sources tabs real; Insights/Activity coming soon |
| `/processes/[id]/graph` | Wired | Yes | `GET /processes/{id}/graph` + `GET /processes/{id}` for confidence |
| `/processes/[id]/timeline` | Wired | Yes | `GET /processes/{id}/timeline` |
| `/admin` | Placeholder | No | Static shell; real data requires admin API integration |

---

## Wired Functionality (real API data)

### Home workspace (`/`)
- Recent workflow cards fetched from `GET /processes` (up to 3)
- Confidence score **not yet available** from the list endpoint; shown as "No score yet"
- Empty state shown when no processes exist

### Upload & run status (`/runs/upload`, `/runs/[id]`)
- File upload to `POST /upload` with multipart form
- Run status polling via `GET /runs/{id}` — sources, artifacts, workflow events displayed
- Extraction summary shown when available

### ProcessIR review (`/runs/[id]/review`)
- Entities and relations from ProcessIR displayed grouped by type
- Accept / Reject / Edit controls POST to review endpoints
- Taxonomy feedback form operational

### Process exploration (`/processes`)
- Full process list with filter
- Similarity groups panel from `GET /processes/groups`
- Links to narrative, graph, timeline per process

### Workflow narrative (`/processes/[id]`)
- **Narrative tab:** Summary, key findings, and at-a-glance stats derived from ProcessIR
- **Confidence ring:** Score derived from `confidence_summary` population ratio
- **Sources tab:** Run metadata — source files (filename, type, size, date, status) and extraction artifacts (type, size, retention class)
- **Workflow tab:** Redirects to graph view
- **Insights / Activity tabs:** Marked "coming soon"

### Spatial workflow graph (`/processes/[id]/graph`)
- React Flow graph rendered from `GET /processes/{id}/graph`
- Layer toggles (Departments, Systems, Approvals, Exceptions, Controls, Roles) **functional** — filter nodes and edges by type
- Confidence panel shows real score from `GET /processes/{id}` confidence_summary
- Confidence breakdown per dimension (steps, roles, systems, controls, etc.)
- MiniMap and zoom/pan controls operational

### Process timeline (`/processes/[id]/timeline`)
- Change events from `GET /processes/{id}/timeline`
- Category filter operational
- Evidence count and ambiguity warnings displayed

---

## Placeholder / Not-yet-connected Sections

| Section | Location | Status |
|---|---|---|
| Recent activity feed | Home workspace | Static demo data — not connected to run history |
| "Connect approved source" button | Home workspace | Disabled — source connector not built |
| Search bar (⌘K) | Home workspace | UI only — no search backend |
| Notification bell | Home workspace | UI only |
| Confidence score on home cards | Home workflow cards | Not available from list endpoint |
| Share / Export buttons | Graph + Narrative pages | Disabled — not implemented |
| Review & Publish button | Graph page | Disabled — publish pipeline not built |
| AI Suggestions panel | Graph page | Marked "coming soon" — AI analysis not connected |
| Insights tab | Narrative page | Marked "coming soon" |
| Activity tab | Narrative page | Marked "coming soon" |
| Admin overview stats | `/admin` | Placeholder — not connected to real data |
| Admin integrations | `/admin` | All shown as "Disconnected" |
| Admin audit logs | `/admin` | Empty — audit pipeline not connected |
| Admin security posture | `/admin` | Planned controls listed; not enforced |

---

## Admin Portal (`/admin`)

The admin portal shell exists but is **not yet connected to real data**. An amber
banner is displayed on the page to communicate this clearly.

Real data will be available once the admin API stubs (`/admin/*`) are connected to
live governance systems. The API contracts are defined in `services/api/app/routes/admin.py`.

---

## API Routes Powering the UI

| API endpoint | Powers |
|---|---|
| `GET /health` | Health page |
| `GET /ready` | Readiness indicator |
| `POST /upload` | File upload screen |
| `GET /runs/{id}` | Run status page, Sources tab |
| `GET /runs/{id}/process-ir` | Review screen (ProcessIR) |
| `GET /runs/{id}/review` | Review screen (reviews) |
| `POST /reviews/entities/{id}` | Entity review actions |
| `POST /reviews/relations/{id}` | Relation review actions |
| `POST /reviews/taxonomy` | Taxonomy feedback form |
| `GET /processes` | Home cards, process dashboard |
| `GET /processes/groups` | Similarity groups panel |
| `GET /processes/{id}` | Narrative page, graph confidence |
| `GET /processes/{id}/graph` | Graph page |
| `GET /processes/{id}/timeline` | Timeline page |
| `GET /admin/*` | Admin portal (stubs — not yet wired to UI) |

---

## Known Limitations

- **No authentication or session management** — all routes are publicly accessible
- **No search** — process filtering is client-side only, no full-text search backend
- **No export** — Share/Export buttons are disabled
- **Admin portal is fully placeholder** — no real governance data
- **Confidence scores on home cards** — not yet available from list endpoint; shown as "No score yet"
- **AI Suggestions** — panel exists but analysis pipeline is not connected
- **Source connectors** — upload is the only ingestion mechanism; live connectors not built

---

## Design System

Design tokens are defined in `frontend/app/globals.css` as CSS custom properties.
Reference images in `.ai/design/references/` are the canonical visual references for
spacing, typography, card styling, and layout.
