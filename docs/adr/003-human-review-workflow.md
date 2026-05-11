# ADR-003 — Human Review Workflow

## Status

Accepted

## Context

The deterministic extraction pipeline produces ProcessIR artifacts from customer documents.
Extraction quality is high for well-structured inputs, but human expert review remains necessary to:

1. Confirm or correct extracted entities and relations.
2. Override confidence scores where domain context is needed.
3. Provide taxonomy feedback to improve future extraction.
4. Build a labelled supervision corpus for potential future ML retraining.

We need a review data model, API, and UI that integrate with the existing pipeline without
disrupting the extract-first, review-second architecture.

## Decision

### Data model

Four new Postgres tables (Sprint 5, `infra/postgres/init.sql`):

| Table | Purpose |
|---|---|
| `review_sessions` | Groups reviews for a single run. One session per reviewer per run. |
| `entity_reviews` | One row per human decision on a ProcessIR entity. |
| `relation_reviews` | One row per human decision on a ProcessIR relation edge. |
| `taxonomy_feedback` | Freeform taxonomy label suggestions tied to an entity. |

No raw customer content is stored in any review table. All records reference
ProcessIR entity IDs (string IDs from the ProcessIR JSON) and structured metadata only.

### Review states

Both `entity_reviews` and `relation_reviews` share the same finite set of review states:

| State | Meaning |
|---|---|
| `accepted` | Reviewer confirms the extracted item is correct. |
| `rejected` | Reviewer marks the item as incorrect or not relevant. |
| `edited` | Reviewer has changed the label or canonical label. |
| `merged` | Reviewer merged this item into another entity/relation. |
| `split` | Reviewer split this item into multiple entities/relations. |
| `confidence_override` | Reviewer manually set a confidence score. |

### Upsert semantics

Review actions are upserted, not appended. A second review action on the same
`(review_session_id, entity_id)` overwrites the prior state and updates `updated_at`.
This preserves a clean audit record — one authoritative decision per session and entity —
rather than growing a change log.

### Taxonomy feedback types

| Type | Meaning |
|---|---|
| `new_label` | Suggest a new canonical label for this entity. |
| `merge_suggestion` | Suggest this entity should be merged with another. |
| `split_suggestion` | Suggest this entity should be split into sub-entities. |
| `other` | General feedback not covered by other types. |

Taxonomy feedback is append-only (not upserted) to allow multiple suggestions per entity.

### API endpoints

Review endpoints are stateless and follow the same pattern as the rest of the API:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/runs/{run_id}/review` | Return all review sessions, entity reviews, relation reviews, and taxonomy feedback for a run. |
| `POST` | `/reviews/entities/{entity_id}` | Accept, reject, or edit a ProcessIR entity. |
| `POST` | `/reviews/relations/{relation_id}` | Accept, reject, or edit a ProcessIR relation. |
| `POST` | `/reviews/taxonomy` | Submit taxonomy label feedback. |

A `review_session` is created automatically on the first POST if `review_session_id` is not supplied.
`reviewer_id` is a free-form string (e.g. email address) — no authentication system is integrated yet.

### Frontend

The review UI (`frontend/app/runs/[id]/review`) loads ProcessIR data and existing reviews
in parallel, groups entities by type (workflow steps, roles, systems, controls, change events,
decision points), and renders Accept / Reject / Edit controls and a taxonomy feedback form
per entity. Review badges update immediately after each action.

## Consequences

### What this enables

- Human experts can validate, correct, and annotate extracted process intelligence.
- Review decisions persist in Postgres with full audit trails (`created_at`, `updated_at`, `reviewer_id`).
- The `entity_reviews` and `relation_reviews` tables can be queried to generate labelled datasets
  for future supervised ML retraining (see Future path below).
- Taxonomy feedback provides a structured channel for domain experts to improve the gazetteer and
  taxonomy definitions without code changes.

### Current limitations

- No authentication. `reviewer_id` is a self-reported string.
- No multi-reviewer consensus or conflict resolution.
- No undo history — only the most recent review state per session/entity is stored.
- No real-time collaboration.
- Taxonomy feedback is not automatically applied to the gazetteer — it requires a manual
  curation step.

### What this does not do

- Does not trigger LLM retraining automatically.
- Does not modify the ProcessIR artifact in MinIO — reviews are an annotation layer only.
- Does not implement RBAC or tenant isolation.
- Does not provide graph-level relationship visualization.

## Future path: supervised learning

The review tables are designed with future ML supervision in mind:

1. `entity_reviews` rows with `review_state IN ('accepted', 'rejected', 'edited')` provide
   binary and correction labels for each extracted entity.
2. `edited_label` / `edited_canonical_label` columns capture the corrected ground truth.
3. `confidence_override` values can calibrate model confidence thresholds.
4. A future batch job can export `(entity_id, entity_type, original_label, edited_label, review_state)`
   as training examples for a fine-tuning or few-shot prompting pipeline.
5. `taxonomy_feedback` rows with `feedback_type = 'new_label'` can feed into gazetteer expansion.

No retraining infrastructure is implemented in this sprint. The schema is designed to be
compatible with future pipelines without requiring migration.

## Alternatives considered

### Append-only review log

An append-only audit log (one row per action, no upsert) was considered. Rejected because:
- Adds complexity to query the "current" state of a review.
- Makes the API response shape more complex.
- Doesn't add meaningful value for MVP review workflows.

Upsert with `updated_at` preserves enough auditability for the current use case.

### Embedding review state in the ProcessIR artifact

Storing review annotations directly in the MinIO ProcessIR JSON was considered. Rejected because:
- ProcessIR artifacts are treated as durable extraction outputs — mutating them on review
  would blur the boundary between extraction and annotation.
- Postgres provides better query performance and join semantics for review analytics.
- Review state and extraction state should be independently queryable.

### Separate review microservice

Moving review storage to a dedicated service was considered. Rejected for now because:
- The data model is simple enough to colocate with the existing schema.
- Splitting services prematurely adds operational complexity.
- The API layer remains stateless regardless.
