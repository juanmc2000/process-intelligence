# Data Flow — Sprint 1 (Upload → Parsed Artifact)

## Happy Path

```
Client
  │
  │  POST /runs/upload (multipart file)
  ▼
API (FastAPI)
  │  1. Read file bytes, compute SHA-256 hash
  │  2. Create run record in Postgres (status = "uploaded")
  │  3. Create source record in Postgres
  │  4. PUT raw bytes to MinIO  →  minio://artifacts/raw/<run_id>/...
  │  5. Create artifact record in Postgres (artifact_type = "raw")
  │  6. Create workflow_event (event_type = "uploaded")
  │  7. Start Temporal workflow (workflow_id = run_id)
  │
  │  Return UploadResponse { run_id, source_id, artifact_id, status, object_uri }
  ▼
Temporal (IngestionRunWorkflow)
  │
  │  Activity: update_run_to_processing
  │    → Postgres: run.status = "processing"
  │
  │  Activity: parse_artifact
  │    → Read raw artifact from MinIO
  │    → Write stub parsed JSON to MinIO  →  minio://artifacts/parsed/<run_id>/...
  │    → Create artifact record (artifact_type = "parsed")
  │    → Create workflow_event (event_type = "parsed")
  │    → Update source.status = "parsed"
  │    → Return parsed_uri
  │
  │  Activity: complete_run
  │    → Postgres: run.status = "completed"
  │    → Create workflow_event (event_type = "completed")
  ▼
Done. Client may poll GET /runs/{run_id} to observe status transitions.
```

## Status Transitions

```
uploaded → processing → completed
                     ↘ failed
```

## Data Stores

| Store | What is written | Retention |
|---|---|---|
| PostgreSQL | run/source/artifact records, workflow events | Long-lived |
| MinIO `raw/` | Original uploaded file bytes | Deletion-eligible after parsing |
| MinIO `parsed/` | Stub/parsed representation of the artifact | Deletion-eligible after LLM extraction |

## Traceability

Every step threads `run_id` through Postgres records and MinIO object keys.
The `workflow_events` table provides a full audit trail for each run.
