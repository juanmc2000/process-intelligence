# Process Intelligence — Frontend

A minimal Next.js frontend for uploading artifacts and reviewing extracted process intelligence.

## Stack

- Next.js 14 (App Router)
- React 18
- TypeScript
- Tailwind CSS

## Local development

```bash
# Copy and configure the environment
cp .env.local.example .env.local
# Edit .env.local if your API runs on a non-default port

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The app runs at http://localhost:3000 by default.

## Running with Docker Compose

```bash
# From the repository root
docker compose up -d
```

The frontend is available at http://localhost:3000 (or the port set by `FRONTEND_PORT`).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8010` | Base URL of the Process Intelligence API |

## Pages

| Path | Description |
|---|---|
| `/` | Home — links to upload and health |
| `/health` | API health check — probes `/health` and `/ready` |
| `/runs/upload` | Upload an artifact and start a run |
| `/runs/[id]` | Run status and extraction summary |
| `/runs/[id]/review` | ProcessIR review screen |
