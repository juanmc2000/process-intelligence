# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

```bash
# Activate the project virtualenv (Python 3.11)
source .venv-process-intelligence/bin/activate

# Run the API service locally
uvicorn services.api.app.main:app --reload

# Run a worker (example: ingestion)
python -m services.workers.ingestion

# Lint
ruff check .

# Format
black .

# Type check
mypy .

# Run tests
pytest

# Run a single test file
pytest path/to/test_file.py

# Run a single test
pytest path/to/test_file.py::test_function_name

# Validate docker-compose config
docker compose config

# Start the full local stack
docker compose up -d

# Stop the local stack
docker compose down
```

---

## Architecture

This is a Python monorepo for a **process intelligence platform** — it extracts structured process knowledge from customer artifacts (documents, diagrams, etc.) using a pipeline of workers orchestrated by Temporal.

### Repository Layout

```
services/
  api/          # FastAPI service — stateless HTTP layer, delegates heavy work to workers
  workers/
    ingestion/  # Handles artifact intake and storage to MinIO
    parser/     # Parses raw artifacts into text/structured representations
    llm/        # LLM extraction steps — converts parsed text to process IR
    graph/      # Writes process IR into Neo4j graph

packages/
  core/
    schemas/    # Pydantic schemas shared across services
    models/     # ORM/DB models
    database/   # DB session/connection setup
    workflows/  # Temporal workflow and activity definitions
    storage/    # MinIO/S3 object storage client abstraction
    connectors/ # External system connectors
    taxonomy/   # Process taxonomy definitions
    process_ir/ # Process intermediate representation (the core data model)

infra/
  postgres/     # init.sql for local DB bootstrap

docs/
  architecture/ # Architecture decision records and data flow diagrams
  business/     # Business capabilities, user journeys, NFRs
```

### Infrastructure Stack

| Component   | Role                                         |
|-------------|----------------------------------------------|
| FastAPI     | HTTP API layer                               |
| Temporal    | Workflow orchestration for all worker pipelines |
| PostgreSQL  | Transactional metadata, run state, audit records |
| Redis       | Task queuing and short-lived state           |
| MinIO       | Object storage for artifacts and parsed text |
| Neo4j       | Process knowledge graph                      |

### Key Architectural Flows

**Ingestion → Extraction → Graph pipeline:**
1. Client POSTs artifact to API → API creates a `run` record in Postgres and uploads artifact to MinIO, then triggers a Temporal workflow.
2. Temporal routes work through worker activities: `ingestion` → `parser` → `llm` → `graph`.
3. Each step reads/writes to MinIO and logs metadata to Postgres. The `run_id` threads through all steps for traceability.
4. Final structured process data is written into Neo4j.

**Data lifecycle:**
- Raw artifacts and parsed text in MinIO are temporary and deletion-ready.
- Postgres stores only run state, URIs, and structured extraction records.
- Neo4j holds the long-lived process intelligence graph.

### Worker Pattern

All four workers (`ingestion`, `parser`, `llm`, `graph`) share one Docker image (`services/workers/Dockerfile`) and are launched with different entry-point commands. Each is independently scalable. Workers must be retry-safe and idempotent.

### API Contract

The API is stateless. It must not do long-running work inline. All heavy processing is delegated to Temporal workflows. Required endpoints: `GET /health`, `GET /ready`.

---

## Architecture Principles

- FastAPI APIs must remain stateless.
- Long-running or heavy processing must run in workers via Temporal workflows.
- Services must be independently containerized.
- Use object storage (MinIO/S3) instead of local filesystem storage.
- Store only minimal structured process intelligence long term.
- Raw customer artifacts and parsed text are temporary and deletion-ready.
- Design all services to be Kubernetes-compatible later, but do not introduce Kubernetes complexity now.
- Prefer simple implementations over premature abstractions.

---

## Coding Standards

- Prefer functional programming patterns in Python unless OOP provides clear benefits.
- Keep functions small, composable, and explicit.
- Use type hints.
- Use Pydantic for schemas and validation.
- Write clear comments only where intent or reasoning is non-obvious.
- Avoid redundant comments that restate the code.
- Avoid hidden side effects and global mutable state.
- Keep business logic separate from infrastructure/runtime concerns.

---

## AI / LLM Guardrails

- Prefer deterministic logic before introducing LLMs.
- Do not introduce agents or orchestration frameworks unless explicitly requested.
- All LLM outputs must validate against structured schemas.
- Avoid unnecessary LLM calls and avoid AI overengineering.
- Cache repeatable LLM operations where appropriate.

---

## Infrastructure Rules

- Do not store important state in containers.
- Do not rely on local filesystem persistence.
- Use environment variables for configuration.
- All services must expose health/readiness endpoints where appropriate.
- All processing runs must be traceable via run_id.

---

## Development Rules

- Do not introduce new frameworks or major dependencies without approval.
- Do not redesign architecture unless explicitly requested.
- Extend existing patterns before introducing new abstractions.
- Keep implementations production-shaped, but minimal.

---

## Database

- All schema changes require migration files. No undocumented schema edits.
- Store object storage URIs in Postgres, not binary data.
- Audit-relevant records should include: `input_hash`, `artifact_uri`, `schema_version`, `prompt_version`, `model_name`, `output_json`, `created_at`, `updated_at`, `processing_status`, `error_message`.
- Early core tables: `runs`, `sources`, `artifacts`, `extraction_versions`, `workflow_events`.

---

## Testing

- Add smoke tests for critical end-to-end flows.
- Prefer integration tests for workflows and infrastructure interactions.
- Ensure processing steps are idempotent where possible.

---

## Documentation

- Record important architectural decisions in `docs/adr/`.
- Keep architecture and data-flow documentation aligned with implementation.
