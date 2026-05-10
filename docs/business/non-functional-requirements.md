# Non-Functional Requirements

## Data Minimisation and Zero-Retention

- Raw customer artifacts must never be stored in Postgres or application logs.
- Only URIs and structural metadata (hashes, sizes, versions) are stored in Postgres.
- Raw and normalized artifacts are explicitly temporary (`retention_class='temporary'`).
- ProcessIR is the only durable artifact class (`retention_class='durable'`).
- A future scheduled job must be the sole mechanism for physical artifact deletion.
- No raw customer content may appear in API responses at any route.

## Privacy and Security

- All artifact storage paths are opaque URIs — no customer-identifiable information in paths.
- Extraction results must contain structured process facts only, not verbatim customer text.
- `model_invocations` table must not store LLM prompts or raw responses.
- All processing must be traceable via `run_id` across Postgres, MinIO, and Temporal.

## Reliability

- All Temporal activities must be idempotent and retry-safe.
- Worker failures must result in `run.status = 'failed'` — not silent stalls.
- Pipeline steps must not silently discard errors; all failures must be recorded in `workflow_events`.

## Observability

- Every pipeline transition must produce a `workflow_events` row.
- `extraction_runs.status` must reflect current extraction state at all times.
- `GET /runs/{run_id}` must expose the full run state including extraction summary.

## Schema Governance

- All artifact JSON content must be validated against a versioned Pydantic schema before writing.
- Schema version strings must be recorded in both the artifact JSON and the Postgres record.
- Breaking schema changes require a new version string and migration plan.

## Performance

- `GET /runs/{run_id}` must respond within 500ms under normal load.
- The full upload-to-ProcessIR pipeline must complete within 90 seconds for artifacts under 10 MB.
