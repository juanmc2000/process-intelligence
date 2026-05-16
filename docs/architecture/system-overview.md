# System Overview

## Purpose

Process Intelligence extracts structured process knowledge from customer artifacts
(documents, diagrams, slide decks) and stores it in a queryable knowledge graph.

## Services

| Service | Technology | Role |
|---|---|---|
| `api` | FastAPI | Stateless HTTP layer — accepts uploads, returns run status |
| `parser-worker` | Temporal Python SDK | Executes the ingestion workflow; parses raw artifacts |
| `postgres` | PostgreSQL 16 | Run state, source and artifact metadata, workflow events |
| `minio` | MinIO | Object storage for raw artifacts and parsed text |
| `temporal` | Temporal auto-setup | Workflow orchestration and activity scheduling |
| `temporal-ui` | Temporal UI | Workflow visibility |

## Repository Layout

```
services/
  api/            FastAPI application
  workers/
    parser/       Temporal worker for the ingestion task queue
      pdf.py      PDF text extraction and image candidate detection
      eml.py      EML header/metadata extraction (no body content stored)
      zip.py      ZIP expansion with path-traversal protection
      image_candidates.py  Rule-based image candidate scoring

packages/
  core/
    database/     psycopg2 session and SQL repository helpers
    storage/      MinIO client factory and object-key utilities
    workflows/    Temporal workflow and activity definitions
    schemas/      Pydantic schemas: NormalizedEvidence, ProcessIR
    process_ir/   Deterministic extraction: gazetteer, patterns, classifier, relations, evaluation

infra/
  postgres/       init.sql — Sprint 1–3 schema bootstrap

tests/
  smoke/          End-to-end smoke tests (require docker compose up)
  unit/           Unit tests for parser modules (no infrastructure required)
  integration/    Integration tests for format dispatch (no infrastructure required)
```

## Supported Upload Formats

| Format | Detection | Notes |
|---|---|---|
| PDF | `.pdf` extension or `application/pdf` MIME | Text-readable only; no OCR |
| EML | `.eml` extension or `message/rfc822` MIME | Headers and structure only; body text not stored |
| ZIP | `.zip` extension or `application/zip` MIME | Expands `.pdf`, `.eml`, `.txt`, `.md` children; nested ZIPs skipped |
| TXT / MD / other | Fallback | Character count and hash only |

See `docs/architecture/data-flow.md` for full format behaviour and limits.

## Frontend

| Item | Value |
|---|---|
| Framework | Next.js 14, TypeScript, Tailwind CSS |
| Graph | React Flow |
| Docker port | 3000 |
| API client | `frontend/lib/api.ts` |
| Base URL env var | `NEXT_PUBLIC_API_URL` (default: `http://localhost:8010`) |

See `docs/architecture/ui-state.md` for full route inventory and placeholder status.

## API Routes

| Prefix | Module | Purpose |
|---|---|---|
| `/upload` | `routes/upload.py` | Multi-file ingestion |
| `/runs` | `routes/runs.py` | Run status, ProcessIR, review |
| `/reviews` | `routes/review.py` | Entity/relation/taxonomy review actions |
| `/processes` | `routes/processes.py` | Process exploration, graph, timeline |
| `/admin` | `routes/admin.py` | Admin/security governance stubs |
| `/health`, `/ready` | `main.py` | Health and readiness endpoints |

## Ports (local)

| Service | Port |
|---|---|
| API | 8010 |
| Frontend | 3000 |
| PostgreSQL | 5442 |
| MinIO API | 9010 |
| MinIO Console | 9011 |
| Temporal gRPC | 7233 |
| Temporal UI | 8088 |
