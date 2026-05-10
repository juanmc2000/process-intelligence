# Milestone Checkpoints

---

## Sprint 1 — Upload to Parsed Artifact

**Goal:** A client can upload a file, the system stores it, orchestrates parsing via Temporal,
and returns a terminal run status with artifact references.

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

---

## Sprint 2 — Normalized Evidence and ProcessIR Extraction

**Goal:** The pipeline produces schema-valid NormalizedEvidence and ProcessIR artifacts.
No raw customer content is stored or returned. Extraction status is visible via the API.

### DATA-003 — Extraction tables
- [ ] `normalized_evidence`, `extraction_runs`, `extraction_results`, `model_invocations` tables exist
- [ ] Tables support schema versioning and status tracking
- [ ] No raw customer content stored in any table

### SCHEMA-001 — Core schemas
- [ ] `NormalizedEvidenceSchema` defined in `packages/core/schemas/`
- [ ] `ProcessIR` schema with all sub-types defined in `packages/core/schemas/process_ir.py`
- [ ] Schemas re-exported from `packages/core/process_ir/`

### PARSER-001 — Normalized evidence artifact
- [ ] Parser writes `normalized_evidence.json` to MinIO (no raw content)
- [ ] `normalized_evidence` DB record created per parse
- [ ] Source status updated to `parsed`

### LLM-001 — ProcessIR extraction stub
- [ ] `extract_process_ir` activity runs after parse
- [ ] Writes schema-valid ProcessIR JSON to MinIO `process_ir/`
- [ ] `extraction_runs` record created with status transitions
- [ ] `extraction_results` record created with `process_ir_uri`
- [ ] No external LLM calls made

### API-004 — Extraction summary in run status
- [ ] `GET /runs/{run_id}` includes `extraction` field
- [ ] Extraction field includes `extraction_run_id`, `status`, `process_ir_uri`
- [ ] Returns `extraction: null` for runs without extraction
- [ ] No raw content in response

### SEC-001 — Artifact retention lifecycle
- [ ] `artifacts` table has `retention_class` and `purge_after` columns
- [ ] Raw artifacts: `retention_class='temporary'`, `deletion_eligible=True`
- [ ] Normalized evidence: `retention_class='temporary'`, `deletion_eligible=True`
- [ ] ProcessIR: `retention_class='durable'`, `deletion_eligible=False`
- [ ] Purge lifecycle documented in ADR-001

### TEST-002 — Extended smoke test
- [ ] Smoke test validates `normalized_evidence` artifact exists and is temporary
- [ ] Smoke test validates `process_ir` artifact exists and is durable
- [ ] Smoke test validates extraction summary in run status response
- [ ] Smoke test confirms no raw customer content in API response
- [ ] `make smoke` runs the test suite

### DOC-002 — ADR and data-flow documentation
- [ ] ADR-001 documents the four artifact tiers and zero-retention rationale
- [ ] `docs/architecture/data-flow.md` updated to reflect Sprint 2 pipeline
- [ ] Milestone checkpoints updated

---

## Sprint 3 — Multi-Format Ingestion and Image Candidate Detection

**Goal:** The pipeline handles PDF, EML, ZIP, and generic uploads. Multi-file uploads are supported.
ZIP files are expanded into child sources. Image candidates are detected rule-based (no OCR/vision).
No raw content is stored or returned at any stage.

### DATA-004 — Source lineage metadata
- [ ] `sources` table carries `source_date`, `author`, `subject`, `sender`, `recipients`, `message_id`, `thread_id`, `original_filename`, `mime_type`, `file_extension`, `parent_source_id`, `parent_artifact_id`
- [ ] Migration applied; no data loss on existing rows

### PARSER-002 — PDF parsing
- [ ] `parse_pdf(data, filename)` returns `format`, `page_count`, `text_char_count`, `image_count`, `content_hash`, `image_candidates`
- [ ] `is_pdf(content_type, filename)` correctly identifies PDF files
- [ ] Uses `pypdf` (pure Python); no OCR

### PARSER-003 — EML parsing
- [ ] `parse_eml(data, filename)` returns headers and structural metadata only
- [ ] Body text char count included; raw body never stored or returned
- [ ] Attachment names and sizes listed in `attachment_metadata`

### PARSER-004 — ZIP expansion
- [ ] `inspect_zip(data, filename)` returns ZIP metadata and child entries
- [ ] Supported children: `.pdf`, `.eml`, `.txt`, `.md`
- [ ] Path traversal rejected; nested ZIPs skipped; 50 MB per-member limit
- [ ] Child sources created with `parent_source_id` referencing the ZIP source

### PARSER-005 — Image candidate detection
- [ ] `score_candidates(filename, format_metadata, reader)` returns candidate list
- [ ] Filename-keyword detection: `flow`, `workflow`, `process`, `diagram`, `map`, `swimlane`, `chart`, `bpmn`, etc.
- [ ] PDF page-level heuristics: low text density and keyword text signals
- [ ] No OCR, no vision model, no network calls

### API-005 — Multi-file upload
- [ ] `POST /runs/upload` accepts 1–20 files (configurable via `UPLOAD_MAX_FILES`)
- [ ] Per-file size limit 50 MB (configurable via `UPLOAD_MAX_SIZE_MB`)
- [ ] Returns `{ run_id, status, sources: [{ source_id, artifact_id, filename, object_uri }] }`
- [ ] One Temporal workflow started per source (workflow_id = `{run_id}-{source_id}`)

### TEST-003 — Parser fixture tests
- [ ] `tests/integration/test_parser_dispatch.py` covers PDF, EML, ZIP, and generic fallback
- [ ] Tests use synthetic in-memory fixtures; no DB, MinIO, or Temporal required
- [ ] All 12 integration tests pass

### DOC-003 — Ingestion format documentation
- [ ] `docs/architecture/data-flow.md` documents supported formats, limits, and ZIP/image-candidate behaviour
- [ ] `docs/architecture/system-overview.md` lists supported formats and parser module layout
- [ ] `docs/business/milestone-checkpoints.md` Sprint 3 section added
- [ ] `docs/business/non-functional-requirements.md` upload limits and ZIP safety documented

---

## Definition of Done (per Sprint)

All checkpoints for the sprint pass. The smoke test suite runs green against
`docker compose up -d`. No critical errors in service logs. No raw customer
content in Postgres, API responses, or worker logs.
