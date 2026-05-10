# Sprint 1 Milestone Checkpoints

## Goal

Deliver a working upload-to-parsed-artifact pipeline: a client can upload a file,
the system stores it, orchestrates parsing via Temporal, and returns a terminal
run status with artifact references.

## Checkpoints

### INFRA-001 — Docker Compose stack
- [ ] `docker compose up -d` starts all services without errors
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `GET /ready` returns `{"status": "ok"}` (Postgres and MinIO reachable)
- [ ] Temporal UI accessible at `http://localhost:8088`

### DATA-001 — Postgres schema
- [ ] `runs`, `sources`, `artifacts`, `workflow_events` tables created by `init.sql`
- [ ] UUID primary keys via `pgcrypto` extension
- [ ] Foreign keys with correct cascade behaviour

### STORAGE-001 — MinIO client
- [ ] `make_storage_client()` connects to MinIO using env vars
- [ ] Deterministic `make_object_key()` produces collision-resistant paths
- [ ] `object_uri()` returns `minio://<bucket>/<key>` strings

### API-001 — Health endpoints
- [ ] `GET /health` always returns 200
- [ ] `GET /ready` checks Postgres and MinIO connectivity

### API-002 — Upload endpoint
- [ ] `POST /runs/upload` accepts multipart file up to 100 MB
- [ ] Returns 413 for oversized files
- [ ] Creates run, source, artifact records in Postgres
- [ ] Stores raw bytes in MinIO
- [ ] Triggers `IngestionRunWorkflow` via Temporal

### API-003 — Run status endpoint
- [ ] `GET /runs/{run_id}` returns run with sources, artifacts, workflow_events
- [ ] Returns 404 for unknown run_id

### WORKFLOW-001 — Ingestion workflow
- [ ] `IngestionRunWorkflow` drives `uploaded → processing → completed | failed`
- [ ] Activities are retry-safe and idempotent
- [ ] Failure in `parse_artifact` sets run status to `failed`

### WORKER-001 — Parser worker
- [ ] `docker compose up parser-worker` connects to Temporal without errors
- [ ] Worker polls `ingestion` task queue and executes workflows end-to-end

### TEST-001 — Smoke tests
- [ ] `pytest tests/smoke/test_upload_pipeline.py` passes against a live stack
- [ ] Upload completes with `status = "completed"` and a `parsed` artifact present

## Definition of Done

All checkpoints above pass. The smoke test suite runs green against
`docker compose up -d`. No critical errors in service logs.
