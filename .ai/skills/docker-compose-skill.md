# Docker Compose Skill

## Purpose

Use this skill when creating or reviewing Docker Compose infrastructure for the Process Intelligence platform.

## Rules

- Each long-running application component must be a separate Compose service.
- Services must be independently restartable.
- Do not rely on local filesystem state except intentional development volumes.
- Use environment variables for all runtime configuration.
- Use `.env` for local values and `.env.example` for safe placeholders.
- Do not commit secrets.
- Use named volumes for infrastructure services such as Postgres, Redis, Neo4j, MinIO, and Temporal.
- Application containers should log to stdout/stderr.
- Do not put business logic into container startup commands.
- Prefer simple, explicit Compose configuration over clever abstractions.

## Required Services For Phase 1

Minimum stack:

- api
- worker or separate workers
- postgres
- redis
- minio
- neo4j
- temporal
- temporal-ui

## Worker Pattern

Use one shared worker image initially, with different service commands:

- ingestion-worker
- parser-worker
- llm-worker
- graph-worker

Each worker must be separately scalable later.

## Checklist

Before completing a Docker Compose change:

- `docker compose config` succeeds
- services have clear names
- env vars are documented
- volumes are intentional
- ports are only exposed where needed
- service dependencies are explicit but not relied on as readiness guarantees
- the design can map to Kubernetes Deployments later

## Output Expected

When applying this skill, provide:

- files changed
- services added or changed
- environment variables added
- volumes added
- risks or follow-up actions