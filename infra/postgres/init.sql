-- Process Intelligence Platform — Postgres bootstrap
-- Sprint 1 schema: runs, sources, artifacts, workflow_events
-- Uses UUID primary keys throughout. No raw customer content is stored.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------
-- runs: top-level processing unit for a customer submission
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status          TEXT NOT NULL DEFAULT 'uploaded',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    error_message   TEXT
);

-- ----------------------------------------------------------------
-- sources: a single customer-supplied input linked to a run
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    content_type    TEXT,
    size_bytes      BIGINT,
    input_hash      TEXT,
    status          TEXT NOT NULL DEFAULT 'uploaded',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sources_run_id_idx ON sources(run_id);

-- ----------------------------------------------------------------
-- Sprint 3 schema: source metadata for document and email lineage
-- ----------------------------------------------------------------

-- Document/email lineage fields on sources.
-- None of these columns store raw content — metadata only.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS source_date       TIMESTAMPTZ;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS author            TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS subject           TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS sender            TEXT;
-- recipients stored as a JSON array of address strings
ALTER TABLE sources ADD COLUMN IF NOT EXISTS recipients        JSONB;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS message_id        TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS thread_id         TEXT;
-- original_filename preserves the name before any normalisation
ALTER TABLE sources ADD COLUMN IF NOT EXISTS original_filename TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS mime_type         TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS file_extension    TEXT;
-- parent references for files extracted from a ZIP container
ALTER TABLE sources ADD COLUMN IF NOT EXISTS parent_source_id   UUID REFERENCES sources(id) ON DELETE SET NULL;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS parent_artifact_id UUID REFERENCES artifacts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS sources_parent_source_id_idx   ON sources(parent_source_id);
CREATE INDEX IF NOT EXISTS sources_parent_artifact_id_idx ON sources(parent_artifact_id);

-- ----------------------------------------------------------------
-- artifacts: stored objects in object storage (raw or parsed)
-- No raw customer content is stored here, only URIs.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artifacts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    source_id           UUID REFERENCES sources(id) ON DELETE SET NULL,
    artifact_type       TEXT NOT NULL,
    -- artifact_type values:
    --   'raw'                  — original customer upload (MinIO raw/)
    --   'normalized_evidence'  — structured parser output (MinIO normalized/)
    --   'process_ir'           — durable ProcessIR extraction result (MinIO process_ir/)
    object_uri          TEXT NOT NULL,
    content_type        TEXT,
    size_bytes          BIGINT,
    schema_version      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Retention lifecycle support (SEC-001)
    -- retention_class: 'temporary' = delete after next pipeline stage;
    --                  'durable'   = keep until explicitly purged by policy
    retention_class     TEXT NOT NULL DEFAULT 'temporary',
    deletion_eligible   BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ,
    -- purge_after: optional timestamp after which deletion_eligible may be set
    purge_after         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS artifacts_run_id_idx ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS artifacts_source_id_idx ON artifacts(source_id);

-- ----------------------------------------------------------------
-- workflow_events: audit log of Temporal workflow state changes
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workflow_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    payload         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS workflow_events_run_id_idx ON workflow_events(run_id);

-- ----------------------------------------------------------------
-- Sprint 2 schema: extraction pipeline tables
-- ----------------------------------------------------------------

-- normalized_evidence: metadata and URI reference for the normalized parser output.
-- No raw customer content is stored here — only URIs and structural metadata.
CREATE TABLE IF NOT EXISTS normalized_evidence (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    source_id           UUID REFERENCES sources(id) ON DELETE SET NULL,
    artifact_id         UUID REFERENCES artifacts(id) ON DELETE SET NULL,
    artifact_uri        TEXT NOT NULL,
    content_hash        TEXT,
    parser_version      TEXT NOT NULL,
    schema_version      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'ready',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS normalized_evidence_run_id_idx ON normalized_evidence(run_id);

-- extraction_runs: one record per extraction attempt against a normalized evidence artifact.
CREATE TABLE IF NOT EXISTS extraction_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    normalized_evidence_id  UUID REFERENCES normalized_evidence(id) ON DELETE SET NULL,
    schema_version          TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'pending',
    error_message           TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS extraction_runs_run_id_idx ON extraction_runs(run_id);

-- extraction_results: URI reference to the ProcessIR artifact produced by an extraction run.
-- No raw LLM output text is stored here.
CREATE TABLE IF NOT EXISTS extraction_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_run_id   UUID NOT NULL REFERENCES extraction_runs(id) ON DELETE CASCADE,
    run_id              UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    process_ir_uri      TEXT NOT NULL,
    schema_version      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'completed',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS extraction_results_extraction_run_id_idx ON extraction_results(extraction_run_id);
CREATE INDEX IF NOT EXISTS extraction_results_run_id_idx ON extraction_results(run_id);

-- model_invocations: audit record for each model call.
-- Populated when a real LLM is invoked; stub runs may omit rows.
-- Supports reproducibility tracking via model_name + prompt_version.
CREATE TABLE IF NOT EXISTS model_invocations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_run_id   UUID NOT NULL REFERENCES extraction_runs(id) ON DELETE CASCADE,
    model_name          TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    input_token_count   INTEGER,
    output_token_count  INTEGER,
    status              TEXT NOT NULL DEFAULT 'completed',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------
-- Sprint 5 schema: human review and feedback tables
-- No raw customer content is stored. All reviews reference
-- ProcessIR entity/relation IDs and structured metadata only.
-- ----------------------------------------------------------------

-- review_sessions: groups entity and relation reviews for a single run.
-- reviewer_id is a free-form string (e.g. email) — no auth system yet.
CREATE TABLE IF NOT EXISTS review_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    reviewer_id     TEXT,
    -- status: open | completed | abandoned
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS review_sessions_run_id_idx ON review_sessions(run_id);

-- entity_reviews: one row per human decision on a ProcessIR entity.
-- entity_type mirrors ProcessIR entity categories (workflow_step, role, etc.).
-- review_state values: accepted | rejected | edited | merged | split | confidence_override
-- edited_label / edited_canonical_label hold new values only when review_state = 'edited'.
-- confidence_override is only populated when review_state = 'confidence_override'.
CREATE TABLE IF NOT EXISTS entity_reviews (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_session_id       UUID NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    run_id                  UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    -- entity_type: workflow_step | role | system_touchpoint | control | exception
    --              | change_event | decision_point
    entity_type             TEXT NOT NULL,
    -- entity_id references the id field inside the ProcessIR JSON (not a FK)
    entity_id               TEXT NOT NULL,
    -- review_state: accepted | rejected | edited | merged | split | confidence_override
    review_state            TEXT NOT NULL,
    original_label          TEXT,
    edited_label            TEXT,
    original_canonical_label TEXT,
    edited_canonical_label  TEXT,
    -- confidence_override: reviewer-supplied confidence score (0.0–1.0)
    confidence_override     NUMERIC(4,3),
    reviewer_note           TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS entity_reviews_session_id_idx ON entity_reviews(review_session_id);
CREATE INDEX IF NOT EXISTS entity_reviews_run_id_idx     ON entity_reviews(run_id);
-- unique constraint allows upsert on (session, entity)
CREATE UNIQUE INDEX IF NOT EXISTS entity_reviews_session_entity_uidx
    ON entity_reviews(review_session_id, entity_id);

-- relation_reviews: one row per human decision on a ProcessIR relation.
-- Relations are modelled as directed edges between two ProcessIR entity IDs.
-- review_state values match entity_reviews for consistency.
CREATE TABLE IF NOT EXISTS relation_reviews (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_session_id   UUID NOT NULL REFERENCES review_sessions(id) ON DELETE CASCADE,
    run_id              UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    -- relation_type: free-form label (e.g. 'uses_system', 'performed_by')
    relation_type       TEXT NOT NULL,
    source_entity_id    TEXT NOT NULL,
    target_entity_id    TEXT NOT NULL,
    -- review_state: accepted | rejected | edited | merged | split | confidence_override
    review_state        TEXT NOT NULL,
    original_label      TEXT,
    edited_label        TEXT,
    reviewer_note       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS relation_reviews_session_id_idx ON relation_reviews(review_session_id);
CREATE INDEX IF NOT EXISTS relation_reviews_run_id_idx     ON relation_reviews(run_id);
-- unique constraint allows upsert on (session, source, target, type)
CREATE UNIQUE INDEX IF NOT EXISTS relation_reviews_session_edge_uidx
    ON relation_reviews(review_session_id, source_entity_id, target_entity_id, relation_type);

-- taxonomy_feedback: reviewer suggestions for improving taxonomy labels.
-- feedback_type: new_label | merge_suggestion | split_suggestion | other
-- Does not store raw customer text — only structured taxonomy suggestions.
CREATE TABLE IF NOT EXISTS taxonomy_feedback (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_session_id   UUID REFERENCES review_sessions(id) ON DELETE SET NULL,
    run_id              UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    entity_type         TEXT NOT NULL,
    entity_id           TEXT NOT NULL,
    -- feedback_type: new_label | merge_suggestion | split_suggestion | other
    feedback_type       TEXT NOT NULL,
    proposed_label      TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS taxonomy_feedback_run_id_idx ON taxonomy_feedback(run_id);
