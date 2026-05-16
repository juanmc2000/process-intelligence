# ADR-005 — Explainability Architecture

**Status:** Accepted
**Sprint:** 8A
**Date:** 2026-05-16

---

## Context

As the process intelligence platform moves toward enterprise adoption, stakeholders need
to understand and trust the extracted process knowledge.  Prior sprints established
deterministic extraction (ADR-002), similarity scoring (ADR-004), and human review
workflows (ADR-003).  Each produces structured facts, but none explains _why_ those
facts exist or _how confident_ the system is in each inference.

Without explainability, reviewers cannot efficiently prioritise their attention, analysts
cannot distinguish well-evidenced findings from speculative inferences, and operators
cannot diagnose quality issues in the extraction pipeline.

---

## Decision

Implement a **deterministic explainability engine** (`packages/core/process_ir/explainability.py`)
that derives explanations purely from ProcessIR structural facts and graph topology.

### Guiding principles

1. **No fabrication** — explanations must reflect only what the data actually contains.
2. **Determinism** — the same ProcessIR always produces the same explanation.
3. **Traceability** — every claim in an explanation must be traceable to a specific
   field, count, or algorithm in the source data.
4. **No LLM dependency** — all logic is rule-based; LLMs are not involved in
   generating or improving explanations.
5. **Non-technical language** — explanations are written for business analysts,
   not engineers.

---

## What is explained

### Entity explanations

Each entity in a ProcessIR (workflow step, role, system, control, decision point,
exception, change event) receives:

- **Confidence tier** derived from evidence reference count:
  - `high` — 4+ evidence refs
  - `medium` — 2–3 refs
  - `low` — 1 ref
  - `unverified` — 0 refs (or entity type structurally lacks refs, e.g. roles)
- **Rationale** — a human-readable sentence explaining the tier
- **Evidence locations** — location hints from evidence refs (page numbers, sections)

Roles are always `unverified` because the `Role` schema carries no `evidence_refs`.
This is intentional and documented, not a deficiency.

### Edge explanations

Each workflow graph edge receives:

- **Basis** — one of: `sequence_order`, `role_assignment`, `system_assignment`,
  `control_heuristic`
- **Rationale** — a human sentence describing the specific relationship

The `control_heuristic` basis explicitly marks edges created by the positional
heuristic in `graph.py` (controls connected to the nearest workflow step by index).
This transparency allows reviewers to know which connections are inferred rather
than extracted.

### Confidence decomposition

The overall confidence score (formula: `50 + (populated_dimensions / 6) * 40`)
is broken down into per-dimension contributions:

| Dimension | Weight |
|---|---|
| Workflow steps | 40% |
| Roles | 20% |
| System touchpoints | 20% |
| Controls | 10% |
| Exceptions | 5% |
| Decision points | 5% |

The decomposition surfaces which dimensions are absent, enabling targeted
collection of missing evidence.

### Evidence lineage summary

Aggregates evidence ref coverage across all entities in a ProcessIR:

- Coverage ratio (entities with at least one ref / total entities)
- Well-evidenced entity labels (2+ refs)
- Unevidenced entity types (all instances of a type have zero refs)
- Human-readable lineage note with coverage tier wording

### Similarity explanations

Wraps `SimilarityScore` (ADR-004) with:

- Verdict: `likely same process` / `possible alias` / `related` / `distinct`
- Per-dimension breakdown with weights and weighted contributions
- Shared label lists per dimension
- Human summary sentence

---

## Testing readiness strategy

### Synthetic dataset approach

Rather than using real customer data, all tests use **synthetic operational workflow
fixtures** in `tests/fixtures/synthetic_workflows.py`.

Fixtures cover five archetypes:
1. **Invoice approval** — standard, well-documented approval with controls
2. **PO escalation** — threshold-based escalation chain with override exception
3. **Payment dispute** — exception handling, change event, sparse evidence example
4. **System outage fallback** — fallback procedure, no system touchpoints
5. **Informal workflow** — sparse documentation, no evidence refs (deliberately low confidence)

Each fixture includes realistic `evidence_refs` to enable coverage ratio testing.
All fixtures are human-readable and document their intended scenario.

### Test coverage targets

| Test category | Tests (Sprint 8A) |
|---|---|
| Entity confidence tiers | 8 |
| Edge explanation basis | 6 |
| Confidence decomposition | 7 |
| Evidence lineage | 7 |
| Similarity explanation | 8 |
| Full bundle / determinism | 5 |
| Integration (synthetic fixtures) | 31 |
| **Total new** | **71** |

All 257 pre-Sprint-8A tests continue to pass (328 total).

---

## API exposure

Three new endpoints expose explainability data:

| Route | Purpose |
|---|---|
| `GET /processes/{id}/explanations` | Full entity/edge/confidence/lineage bundle |
| `GET /processes/{id}/similarity-explanations` | Pairwise similarity explanations vs neighbours |
| `GET /processes/{id}/graph/explanations` | Edge-level rationale for workflow graph |

All endpoints are stateless, return structured facts only, and expose no raw
customer content.  Responses are serialised via `dataclasses.asdict()`.

---

## UI integration

Explainability is surfaced in three places:

- **Narrative page** (`/processes/{id}`) — new "Explanations" tab showing confidence
  decomposition, evidence lineage, and per-entity explanations with tier badges.
  Accessible directly via `?tab=explanations` URL param.
- **Graph page** (`/processes/{id}/graph`) — "Edge reasoning" panel in the right
  sidebar listing each edge's basis and rationale.
- **Processes list** (`/processes`) — enhanced similarity groups panel; "Explain"
  shortcut link on each process card.

---

## Review queue prioritization

Sprint 8A introduces lightweight review queue foundations on the processes list:

- **Review queue summary**: counts by category (Needs review / Processing / Failed / Pending)
- **Category filter tabs**: filter process list by review status
- **Review category badge**: per-process indicator alongside extraction status
- **Priority sort**: completed processes (ready for review) listed first
- **Review button**: direct link to `/runs/{run_id}/review` for completed processes

Review categories are derived from `extraction_status` only — no per-process
confidence calls on the list view.  Full confidence-based prioritisation
requires the list endpoint to expose per-process confidence scores (future work).

---

## Current limitations

- **Roles are always `unverified`** — the `Role` schema does not carry `evidence_refs`.
  A future schema revision could add evidence tracking to roles.
- **Control edges use a positional heuristic** — controls are connected to the nearest
  workflow step by index.  Future work: extract explicit step-to-control relations.
- **Similarity explanations are computed on-demand** — for large process libraries,
  the `similarity-explanations` endpoint may be slow.  Caching or pre-computation
  should be added before production use at scale.
- **Confidence score on processes list** — the list endpoint does not expose confidence
  scores; the processes list page cannot sort by confidence without per-process API
  calls.

---

## Alternatives considered

### LLM-generated explanations

Rejected. LLM explanations are non-deterministic, may fabricate reasoning, and
introduce latency, cost, and unpredictability.  The extraction pipeline is already
deterministic (ADR-002); explainability should match that property.

### Pre-computed explanation cache in Postgres

Deferred.  Acceptable for the current scale.  If explanation generation becomes
a bottleneck, a dedicated `explanation_cache` table (keyed by extraction_result_id
+ schema_version) would be a straightforward addition.

### Embedding-based similarity explanations

Deferred per ADR-004.  The current Jaccard approach is fully explainable and
requires no model inference.  Embedding-based similarity would produce better
results for semantically similar but lexically distinct processes, but sacrifices
full traceability.

---

## Consequences

- Reviewers can see exactly why a workflow entity has low/high confidence and which
  evidence supports it.
- Analysts can prioritise review attention on `unverified` and `low` confidence entities.
- The review queue on the processes list makes it clear which workflows need attention.
- All explainability outputs remain fully deterministic, auditable, and version-stable
  as long as the ProcessIR schema version does not change.
