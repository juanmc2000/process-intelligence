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

packages/
  core/
    database/     psycopg2 session and SQL repository helpers
    storage/      MinIO client factory and object-key utilities
    workflows/    Temporal workflow and activity definitions

infra/
  postgres/       init.sql — Sprint 1 schema bootstrap

tests/
  smoke/          End-to-end smoke tests (require docker compose up)
```

## Ports (local)

| Service | Port |
|---|---|
| API | 8010 |
| PostgreSQL | 5442 |
| MinIO API | 9010 |
| MinIO Console | 9011 |
| Temporal gRPC | 7233 |
| Temporal UI | 8088 |
