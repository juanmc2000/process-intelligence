# Data Flow — Sprint 4 (Upload → Normalized Evidence → Deterministic Extraction → ProcessIR)

## Happy Path

```
Client
  │
  │  POST /runs/upload (multipart, 1–20 files, max 50 MB each)
  ▼
API (FastAPI)
  │  Per request:
  │  1. Validate file count (≤ 20) and each file size (≤ 50 MB)
  │  2. Compute SHA-256 hash for each file
  │  3. Create one run record in Postgres (status = "uploaded")
  │
  │  Per file:
  │  4. Create source record in Postgres
  │  5. PUT raw bytes to MinIO  →  minio://artifacts/raw/<run_id>/...
  │  6. Create artifact record (artifact_type="raw", retention_class="temporary")
  │  7. Create workflow_event (event_type = "uploaded")
  │  8. Start Temporal workflow (workflow_id = "{run_id}-{source_id}")
  │
  │  Return UploadResponse { run_id, status, sources: [{ source_id, artifact_id, filename, object_uri }] }
  ▼
Temporal (IngestionRunWorkflow)
  │
  │  Activity: update_run_to_processing
  │    → Postgres: run.status = "processing"
  │
  │  Activity: parse_artifact
  │    → Download raw bytes from MinIO
  │    → Dispatch to format parser (PDF / EML / ZIP / generic)
  │    → For ZIP: extract supported child files, create child source+artifact records
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
  │    → Download normalized evidence from MinIO to get raw_artifact_uri
  │    → Download raw artifact and extract text (UTF-8 / PDF / EML)
  │    → Run deterministic extraction pipeline:
  │        1. Sentence splitting
  │        2. Negation/speculative filtering
  │        3. Gazetteer matching (systems, roles, departments, controls, etc.)
  │        4. Regex pattern extraction (approvals, rejections, handoffs, etc.)
  │        5. Action classification
  │        6. Relation extraction
  │        7. Temporal cue detection
  │        8. Control relation building
  │        9. Change-event detection
  │    → Convert ExtractionResult to ProcessIR schema
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

## Source Lineage Metadata (Sprint 3)

The `sources` table carries optional lineage fields populated during parsing:

| Field | Purpose |
|---|---|
| `source_date` | Document date or email date (not ingestion date) |
| `author` | Document author or email sender name |
| `subject` | Email subject or document title |
| `sender` | Email From address |
| `recipients` | JSONB array of To addresses |
| `message_id` | Email Message-ID header |
| `thread_id` | Email thread/References header |
| `original_filename` | Filename before any normalisation |
| `mime_type` | MIME type from upload or email part |
| `file_extension` | Lowercased file extension |
| `parent_source_id` | Source ID of the containing ZIP, if applicable |
| `parent_artifact_id` | Artifact ID of the containing ZIP, if applicable |

Child sources extracted from a ZIP reference their parent via `parent_source_id` / `parent_artifact_id`,
preserving full lineage from child file back to the original upload.

No raw document or email body content is stored in Postgres at any stage.

## Supported Ingestion Formats (Sprint 3)

| Format | Detection | Parser module | Metadata extracted |
|---|---|---|---|
| PDF | `application/pdf` MIME or `.pdf` extension | `services/workers/parser/pdf.py` | page_count, text_char_count, image_count, image_candidates |
| EML | `.eml` extension or `message/rfc822` MIME | `services/workers/parser/eml.py` | subject, sender, recipients, cc, source_date, message_id, thread_references, attachment_metadata |
| ZIP | `application/zip` MIME or `.zip` extension | `services/workers/parser/zip.py` | entry_count, extracted_count, skipped_count; supported children stored as child sources |
| TXT / MD | Any other type | `services/workers/parser/` (generic fallback) | file_extension, text_char_count, content_hash |

### Format-Specific Behaviour and Limits

**PDF**
- Text extraction uses `pypdf` (pure Python, no OCR). Image-only PDFs will report `text_char_count=0`.
- Page images are not decoded. Image candidate detection is based on filename keywords and page-level heuristics (low text density, high image count).
- No external vision model or OCR is invoked.

**EML**
- Uses Python stdlib `email` module. No external parsing library.
- Email body text is counted but not stored. Only structural metadata (headers, attachment names/sizes) is retained.
- Attachments are listed as metadata entries; attachment bytes are not extracted by the parser.

**ZIP**
- Supported child extensions: `.pdf`, `.eml`, `.txt`, `.md`. All other extensions are skipped and counted in `skipped_count`.
- Nested ZIPs are skipped (not recursed into).
- Path traversal entries (containing `..`, `//`, or `\`) are rejected silently.
- Each extracted child file becomes a child `source` record with `parent_source_id` pointing to the ZIP source.
- Maximum extracted child size: 50 MB per member.

**Generic fallback**
- Any file that is not PDF, EML, or ZIP falls through to the generic parser.
- Returns `format="generic"`, file extension, character count, and content hash only.

### Image Candidate Detection

Image candidates are detected rule-based only — no OCR, no vision model.
Detection signals (from `services/workers/parser/image_candidates.py`):

| Signal | Confidence |
|---|---|
| Filename contains a diagram keyword (`flow`, `workflow`, `diagram`, `map`, `swimlane`, `chart`, `bpmn`, `flowchart`, `dataflow`, `procedure`) | `low` |
| PDF page has images AND low text density (< 200 chars/image) | `medium` |
| PDF page text contains diagram-reference keywords (`figure`, `fig.`, `diagram`, `flowchart`, etc.) | `low` |

Each candidate includes: `page` (None for filename-based), `location_hint`, `reasons` list, and `confidence` level.

### Upload Limits

| Limit | Default | Override env var |
|---|---|---|
| Max file size | 50 MB | `UPLOAD_MAX_SIZE_MB` |
| Max files per request | 20 | `UPLOAD_MAX_FILES` |

Files exceeding the size limit receive HTTP 413. Requests exceeding the file count limit receive HTTP 422.
