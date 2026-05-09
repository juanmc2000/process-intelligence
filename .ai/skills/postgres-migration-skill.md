# Postgres Migration Skill

## Purpose

Use this skill when creating or reviewing Postgres schema, database access, and migrations.

## Rules

- All schema changes must be represented as migrations.
- Do not make undocumented schema changes.
- Do not rely on manual database edits.
- Use Postgres for transactional metadata, audit records, run state, and structured extraction records.
- Do not store large files or raw binary artifacts in Postgres.
- Store object storage URIs instead.
- Prefer clear constraints over application-only validation.
- Use indexes intentionally.
- Keep migration files deterministic and reviewable.

## Core Phase 1 Tables

Expected early tables may include:

- runs
- sources
- artifacts
- extraction_versions
- workflow_events

Do not overbuild the schema before the first workflow works.

## Auditability Requirements

Where relevant, store:

- input_hash
- artifact_uri
- schema_version
- prompt_version
- model_name
- output_json
- created_at
- updated_at
- processing_status
- error_message

## Checklist

Before completing database changes:

- migration exists
- rollback strategy is clear where appropriate
- constraints are defined
- indexes are justified
- timestamps are included
- object storage URIs are used for artifacts
- naming is consistent
- future pgvector usage is not blocked

## Output Expected

When applying this skill, provide:

- schema changes
- migration files changed
- tables added or changed
- indexes added
- data governance implications
- follow-up database risks