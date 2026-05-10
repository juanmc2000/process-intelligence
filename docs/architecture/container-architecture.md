# Container Architecture

## Docker Compose Services

All services share the `process-intelligence` bridge network and read `.env` for
configuration. Build contexts are set to the project root so that `packages/core`
is accessible inside every container via `PYTHONPATH=/app`.

```
┌──────────────────────────────────────────────────────┐
│  Docker network: process-intelligence                │
│                                                      │
│  ┌───────────┐    ┌──────────────────┐               │
│  │    api    │    │  parser-worker   │               │
│  │ :8000     │    │  (ingestion q)   │               │
│  └─────┬─────┘    └────────┬─────────┘               │
│        │                   │                         │
│        ▼                   ▼                         │
│  ┌──────────┐    ┌──────────────┐   ┌─────────────┐  │
│  │ postgres │    │   temporal   │   │    minio    │  │
│  │ :5432    │    │   :7233      │   │   :9000     │  │
│  └──────────┘    └──────────────┘   └─────────────┘  │
│                         │                            │
│                  ┌──────────────┐                    │
│                  │ temporal-ui  │                    │
│                  │   :8080      │                    │
│                  └──────────────┘                    │
└──────────────────────────────────────────────────────┘
```

## Image Strategy

Both `api` and `parser-worker` are built from the project root context with
separate Dockerfiles. This lets them share the `packages/core` library without
publishing it as a separate package.

```
docker-compose.yml
  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile

  parser-worker:
    build:
      context: .
      dockerfile: services/workers/Dockerfile
    command: python -m services.workers.parser
```

## Environment Configuration

All runtime configuration is injected via environment variables loaded from `.env`.
No secrets are baked into images. Copy `.env.example` to `.env` to get started.

## Volumes

| Volume | Purpose |
|---|---|
| `postgres_data` | Postgres data directory |
| `minio_data` | MinIO object store |

Both volumes survive `docker compose down` but are removed by `docker compose down -v`.
