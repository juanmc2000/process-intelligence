# Kubernetes Readiness Skill

## Purpose

Use this skill to review whether infrastructure and service design can migrate cleanly to Kubernetes later.

This skill does not implement Kubernetes manifests unless explicitly requested.

## Core Principles

- Build with Docker now.
- Do not use Kubernetes yet.
- Design every container as if it will later become a Kubernetes Deployment.
- Keep infrastructure replaceable.
- Keep application services stateless where possible.

## Non-Negotiable Rules

- API services must be stateless.
- Heavy processing must happen in workers, not API requests.
- Persistent files must go to object storage.
- Databases should store metadata and URIs, not large files.
- Configuration must come from environment variables.
- Logs must go to stdout/stderr.
- Workers must be retry-safe.
- Workers must be horizontally scalable.
- Services must tolerate restarts.
- Services must not depend on container-local state.

## Required Health Behavior

API services should expose:

- `/health`
- `/ready`

Workers should support:

- graceful shutdown
- safe restart
- idempotent task execution

## Review Ratings

Use:

- `PASS` when the change is Kubernetes-friendly
- `WARN` when the change is acceptable for now but creates future migration work
- `BLOCK` when the change introduces serious future Kubernetes migration risk

## Checklist

Review for:

- local filesystem dependency
- hardcoded Docker service names in application logic
- hidden state
- singleton assumptions
- non-idempotent workers
- synchronous long-running API work
- missing health/readiness endpoints
- missing environment variables
- unsafe startup assumptions
- unclear scaling model

## Output Expected

When applying this skill, provide:

- PASS/WARN/BLOCK
- reason for rating
- specific risks
- required fixes
- future Kubernetes migration notes