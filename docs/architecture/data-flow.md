# Data Flow — Sprint 2 (Upload → Normalized Evidence → ProcessIR)

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
  │  5. Create artifact record (artifact_type="raw", retention_class="temporary")
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
  │    → Build NormalizedEvidence JSON (metadata only, no raw content)
  │    → Write to MinIO  →  minio://artifacts/normalized/<run_id>/...
  │    → Create artifact record (artifact_type="normalized_evidence", retention_class="temporary")
  │    → Create normalized_evidence record in Postgres
  │    → Update source.status = "parsed"
  │    → Create workflow_event (event_type = "parse_completed")
  │    → Return { normalized_evidence_uri, normalized_evidence_id }
  │
  │  Activity: extract_process_ir
  │    → Create extraction_run record (status = "running")
  │    → Build ProcessIR JSON (deterministic stub — no LLM call)
  │    → Write to MinIO  →  minio://artifacts/process_ir/<run_id>/...
  │    → Create artifact record (artifact_type="process_ir", retention_class="durable")
  │    → Create extraction_result record
  │    → Update extraction_run.status = "completed"
  │    → Create workflow_event (event_type = "extraction_completed")
  │    → Return process_ir_uri
  │
  │  Activity: complete_run
  │    → Postgres: run.status = "completed"
  │    → Create workflow_event (event_type = "completed")
  ▼
Done. Client polls GET /runs/{run_id} to observe status and extraction summary.
```

## Status Transitions

```
uploaded → processing → completed
                     ↘ failed
```

## Data Stores

| Store | What is written | Retention |
|---|---|---|
| PostgreSQL | run/source/artifact records, workflow_events, normalized_evidence, extraction_runs, extraction_results | Long-lived metadata |
| MinIO `raw/` | Original uploaded file bytes | `temporary` — deletion-eligible after parsing |
| MinIO `normalized/` | NormalizedEvidence JSON (metadata only) | `temporary` — deletion-eligible after extraction |
| MinIO `process_ir/` | ProcessIR JSON (structured process facts) | `durable` — not deletion-eligible |

## Artifact Retention Lifecycle

```
raw artifact
  │  deletion_eligible=True, retention_class='temporary'
  │  → eligible for purge after normalized_evidence exists
  ▼
normalized_evidence artifact
  │  deletion_eligible=True, retention_class='temporary'
  │  → eligible for purge after extraction_result exists
  ▼
process_ir artifact
     deletion_eligible=False, retention_class='durable'
     → kept until explicit policy-driven purge
```

Physical deletion is not performed automatically. A future scheduled job reads
`deletion_eligible=True` rows from `artifacts` and removes MinIO objects, then sets `deleted_at`.

## Zero-Retention Guarantee

- No raw customer content is stored in Postgres at any stage.
- No raw customer content appears in API responses.
- Workers must not log raw artifact content.
- ProcessIR fields contain extracted structured facts — not verbatim customer text.

See `docs/adr/001-normalized-evidence-and-process-ir.md` for the full decision record.

## Traceability

Every step threads `run_id` through Postgres records and MinIO object keys.
`workflow_events` provides a full audit trail. `extraction_runs` and `extraction_results`
track each extraction attempt with schema_version for reproducibility.
