# ADR-001: Normalized Evidence and ProcessIR Data Separation

**Status:** Accepted
**Date:** 2026-05-10
**Issues:** DATA-003, SCHEMA-001, PARSER-001, LLM-001, SEC-001, DOC-002

---

## Context

The platform ingests customer-supplied artifacts (documents, diagrams, spreadsheets) and extracts structured process intelligence from them. A naive implementation would store raw file content in Postgres, log parsed text, or mix intermediate and durable data in the same storage layer — creating data minimisation, retention, and auditability problems.

We needed an explicit data contract that separates:
1. Raw customer-supplied input
2. Parser-produced structural metadata
3. LLM extraction results
4. Durable process knowledge

---

## Decision

We separate the pipeline into four distinct artifact tiers, each with its own storage location, schema, and retention class:

### Tier 1 — Raw Artifact (`artifact_type = 'raw'`)
- **Where:** MinIO `raw/<run_id>/`
- **Content:** Original uploaded bytes
- **Schema:** None (opaque blob)
- **Retention:** `temporary` — eligible for deletion after parsing completes
- **In Postgres:** URI only (`artifacts.object_uri`). No file content.

### Tier 2 — Normalized Evidence (`artifact_type = 'normalized_evidence'`)
- **Where:** MinIO `normalized/<run_id>/`
- **Content:** Structural metadata — run_id, source_id, parser_version, schema_version, content_hash, raw artifact URI reference
- **Schema:** `normalized-evidence-v1` (defined in `packages/core/schemas/normalized_evidence.py`)
- **Retention:** `temporary` — eligible for deletion after extraction completes
- **In Postgres:** URI in `artifacts.object_uri` + full record in `normalized_evidence` table

### Tier 3 — Extraction Records
- **Where:** Postgres only
- **Content:** `extraction_runs` and `extraction_results` rows — status, schema_version, ProcessIR URI
- **Retention:** Long-lived audit records. Not deleted unless the run is deleted.
- **In Postgres:** No raw output content stored. `extraction_results.process_ir_uri` points to MinIO.

### Tier 4 — ProcessIR Artifact (`artifact_type = 'process_ir'`)
- **Where:** MinIO `process_ir/<run_id>/`
- **Content:** Structured ProcessIR JSON — workflow steps, decision points, roles, controls, exceptions, change events. All with evidence references to source artifact URIs.
- **Schema:** `process-ir-v1` (defined in `packages/core/schemas/process_ir.py`)
- **Retention:** `durable` — not eligible for deletion. This is the primary output of the platform.
- **In Postgres:** URI in `artifacts.object_uri` + `extraction_results.process_ir_uri`

---

## Zero-Retention Rationale

Customer-supplied documents may contain personally identifiable information, confidential business data, or regulated content. Storing this in Postgres or in application logs violates the principle of data minimisation.

The separation above ensures:
- **Postgres never contains raw customer content.** Only URIs, hashes, and structural metadata.
- **Raw artifacts are explicitly temporary.** They are marked `deletion_eligible=True` and `retention_class='temporary'` from the moment they are stored.
- **Normalized evidence is temporary.** It carries no customer text — only structural references. It can be deleted after extraction.
- **ProcessIR is the only durable output.** It contains structured facts extracted from the artifact, not the artifact itself. No raw customer sentences appear in ProcessIR fields.
- **LLM outputs are never stored verbatim.** The LLM worker produces structured ProcessIR, not free-text output. If a real LLM is used in future, its raw output must not be logged or stored.

---

## Current State vs Target State

| Capability | Sprint 1 | Sprint 2 (this ADR) |
|---|---|---|
| Raw artifact storage | ✅ MinIO raw/ | ✅ unchanged |
| Parsed artifact | Dummy JSON stub | ✅ NormalizedEvidence (no content) |
| Extraction records | None | ✅ extraction_runs + extraction_results |
| ProcessIR | None | ✅ Deterministic stub (schema-valid) |
| Real LLM extraction | None | Planned (Sprint 3+) |
| Artifact purge | Flag only | ✅ retention_class + deletion_eligible + purge_after |
| API extraction visibility | None | ✅ GET /runs/{id} includes extraction summary |

---

## Consequences

- All new pipeline workers must produce schema-validated JSON artifacts.
- Workers must not log raw customer content at any log level.
- ProcessIR schema changes require a new `schema_version` string and migration plan.
- Future physical deletion of temporary artifacts must be implemented as a separate scheduled job that reads `deletion_eligible=True, retention_class='temporary'` from the `artifacts` table and deletes the MinIO objects before setting `deleted_at`.
- `model_invocations` table supports future audit requirements when a real LLM is introduced.
