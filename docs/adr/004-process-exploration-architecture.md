# ADR-004 — Process Exploration Architecture

## Status

Accepted

## Context

After extraction, the system holds a growing library of ProcessIR artifacts — one per document
source, each describing workflow steps, roles, systems, controls, and change events.  Analysts
need to navigate this library, understand how processes relate to one another, and track how
workflows have evolved over time.

Three cross-cutting capabilities are required:

1. **Process identity** — recognise that two ProcessIR instances describe the same operational
   workflow, even when authored independently or extracted from different document versions.

2. **Lineage and evolution** — reconstruct the history of a workflow from its change events and
   identify when one version supersedes another.

3. **Graph visualisation** — render each ProcessIR as an interactive workflow graph in the
   browser, preserving entity IDs so the graph links back to the human review workflow.

All three capabilities must remain deterministic, explainable, and free of LLM calls.

---

## Decision

### 1. Process Identity Strategy — Structural Fingerprints

Each ProcessIR is reduced to a `ProcessFingerprint`: a frozen collection of normalised
(lower-cased) canonical label sets across six structural dimensions:

| Dimension   | Weight |
|-------------|--------|
| Workflow steps | 0.40 |
| Roles       | 0.20  |
| Systems     | 0.20  |
| Controls    | 0.10  |
| Change events | 0.05 |
| Exceptions  | 0.05  |

Similarity between two fingerprints is computed as a **weighted Jaccard score**:

```
similarity(A, B) = Σ weight_i × (|A_i ∩ B_i| / |A_i ∪ B_i|)
```

Empty dimensions (both A and B empty) score 1.0 to avoid penalising processes with narrow scope.

Each dimension produces an individual `DimensionScore` with an overlap list, making every
composite score fully explainable.

**Alias detection** uses union-find on pairs where `score ≥ alias_threshold` (default 0.80).
Transitive aliases are merged into `AliasGroup` objects.

**Candidate clustering** uses single-linkage agglomeration with configurable thresholds:
- `similarity_threshold` (default 0.50): minimum score to share a cluster.
- `merge_threshold` (default 0.80): average intra-cluster score that triggers a merge
  recommendation.

All scoring is deterministic and O(n²) in the number of processes.  For the current scale
(hundreds, not millions, of processes) this is acceptable.  Embeddings are explicitly excluded
from this layer to preserve explainability and avoid inference infrastructure.

### 2. Lineage Strategy — Version Chains and Change Events

Process lineage is reconstructed from two signals:

1. **Ordered version lists** supplied by the caller via `build_lineage_chain(ordered_versions)`.
   The caller (API, worker, or script) determines chronological order — the engine does not
   infer dates from text.

2. **Change events** embedded in each ProcessIR's `change_events` list.  These are categorised
   deterministically into:
   - `role_change`
   - `system_migration`
   - `control_change`
   - `approval_change`
   - `workflow_step_change`
   - `general`

Each `TimelineEvent` preserves `evidence_refs` from the source ChangeEvent for full
traceability back to the original document.

**Superseded-process detection** is a lightweight heuristic: a process is flagged as superseded
if its workflow-step set is a strict subset of another process's step set AND the other process
contains change events (signalling deliberate evolution).  Ambiguous cases (multiple successors)
are flagged explicitly rather than resolved automatically.

**Change aggregation** (`aggregate_changes`) collects events across an arbitrary list of
ProcessIR instances and groups them by category — useful for building dashboards showing the
distribution of change types across the knowledge graph.

No LLM reasoning is used at any point.  Conflicting lineage signals are flagged as ambiguous
and surfaced to human reviewers.

### 3. Graph Projection Architecture — Stateless ProcessIR → React Flow

The graph projection layer (`project_graph`) converts a single ProcessIR instance into a
React Flow-compatible JSON payload.  It is **stateless** — the same ProcessIR always produces
the same graph.

#### Node types

| Node type      | ProcessIR source           |
|----------------|---------------------------|
| `workflow_step` | `workflow_steps`          |
| `role`          | `roles`                   |
| `system`        | `system_touchpoints`      |
| `control`       | `controls`                |
| `decision`      | `decision_points`         |
| `exception`     | `exceptions`              |

#### Edge types

| Edge type        | Source                                       |
|-----------------|----------------------------------------------|
| `precedes`       | Consecutive steps with `sequence_order` set  |
| `involves_role`  | Step → Role via `step.role`                  |
| `executed_in`    | Step → System via `step.system`              |
| `validates`      | Control → nearest step (position heuristic)  |

Entity and relation IDs from the source ProcessIR are preserved in the output, enabling the
frontend to navigate from a graph node directly to the corresponding entity review.

#### Layout hints

Nodes receive column-based x/y position hints based on their type (roles → steps → systems
→ controls → decisions).  This produces a readable initial layout without requiring a full
graph-layout algorithm on the server.  The frontend may reposition nodes freely.

#### Orphan guard

Before returning, the projection removes any edge whose source or target node ID does not exist
in the node list.  This prevents React Flow rendering errors when ProcessIR relationships
reference entities that were not extracted.

### 4. React Flow Payload Model

The `WorkflowGraph.to_react_flow()` method produces:

```json
{
  "processId": "...",
  "nodes": [
    {
      "id": "step_id",
      "type": "workflow_step",
      "data": { "label": "Approve Invoice", "role": "Finance Manager", ... },
      "position": { "x": 220, "y": 0 }
    }
  ],
  "edges": [
    {
      "id": "edge_seq_s0_s1",
      "source": "s0",
      "target": "s1",
      "type": "precedes",
      "label": "precedes"
    }
  ],
  "metadata": {
    "node_count": 7,
    "edge_count": 5,
    "node_type_counts": { "workflow_step": 4, "role": 2, "system": 1 }
  }
}
```

This payload is consumed directly by the React Flow canvas in the frontend.

### 5. API Surface

| Endpoint | Description |
|---|---|
| `GET /processes` | Paginated list of completed extraction results |
| `GET /processes/groups` | Similarity-based clusters (configurable threshold) |
| `GET /processes/{id}` | Full ProcessIR with confidence summary |
| `GET /processes/{id}/timeline` | Change timeline with categorised events |
| `GET /processes/{id}/graph` | React Flow-compatible workflow graph |

All endpoints return structured facts only.  No raw customer content is exposed.

---

## Consequences

### Positive

- Deterministic, explainable similarity and lineage — no opaque ML models.
- Fully testable with synthetic fixtures.
- Graph projection is stateless and easily cacheable.
- API endpoints can be called independently; no shared mutable state.
- Entity IDs preserved end-to-end: graph nodes link back to review records.

### Negative / Limitations

- Similarity is structural (label overlap) rather than semantic.  Two workflows described with
  different vocabulary but identical meaning may score low.
- Lineage chain ordering must be supplied by the caller — the engine does not infer dates.
- Clustering is O(n²) — adequate for the current scale but will need a faster algorithm if
  the process library grows to tens of thousands of entries.
- Control → step edges use a position heuristic, not extracted relations.  Precision will
  improve when explicit step-to-control relations are extracted by the LLM worker.

---

## Future Path

### Embedding-enhanced similarity (future)

A lightweight embedding similarity signal (e.g. sentence-transformers) can be added as an
additional dimension in `score_similarity` behind the existing interface without changing
callers.  The deterministic Jaccard baseline remains the primary signal; embeddings become
a tie-breaker.

### Dedicated graph database (future, see ADR-001)

The projection layer produces payloads suitable for writing into Neo4j.  When the system
moves to graph-DB persistence, `project_graph` output becomes the canonical input to the
Neo4j write activity in the graph worker.  The API can then serve graph queries directly
from the graph DB rather than recomputing projections per request.

### Lineage date inference (future)

If document dates become available via the parser metadata (`source_date` in the `sources`
table), the lineage engine can use them to sort versions chronologically without requiring
caller-supplied ordering.

---

## Related Decisions

- ADR-001 — Normalised evidence and process IR tiers
- ADR-002 — Deterministic extraction
- ADR-003 — Human review workflow
