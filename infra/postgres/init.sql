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
-- artifacts: stored objects in object storage (raw or parsed)
-- No raw customer content is stored here, only URIs.
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artifacts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    source_id           UUID REFERENCES sources(id) ON DELETE SET NULL,
    artifact_type       TEXT NOT NULL,   -- 'raw' | 'parsed'
    object_uri          TEXT NOT NULL,
    content_type        TEXT,
    size_bytes          BIGINT,
    schema_version      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- retention / deletion support
    deletion_eligible   BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at          TIMESTAMPTZ
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
