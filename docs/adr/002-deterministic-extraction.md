# ADR-002: Deterministic Extraction Architecture

**Status:** Accepted
**Date:** 2025-05-11

## Context

Sprint 4 introduces the first real extraction capability — converting parsed text evidence into structured ProcessIR entities, relations, and action classifications. The extraction must work without external LLM calls, operating entirely on deterministic, rule-based algorithms.

## Decision

### Why deterministic extraction first

1. **Baseline quality** — deterministic rules produce interpretable, reproducible results that serve as a baseline for later LLM-assisted extraction.
2. **No external dependencies** — no API keys, no network calls, no model hosting costs.
3. **Auditability** — every extraction carries a `method` field (`gazetteer`, `alias`, `regex`, `rule`, `temporal_cue`) explaining how it was derived.
4. **Speed** — deterministic extraction completes in milliseconds, keeping the pipeline fast.

LLM-assisted extraction is planned for a future sprint. It will run as an alternative or supplementary extraction path, not a replacement.

### Algorithm boundaries

The extractor (`packages/core/process_ir/extractor.py`) runs a 10-step pipeline:

1. **Sentence splitting** — split input on `.!?\n` boundaries.
2. **Negation/speculative filtering** — sentences containing negation markers or speculative language are excluded from factual extraction.
3. **Gazetteer matching** — dictionary-based lookup for known systems, departments, roles, controls, actions, exceptions, and workflow objects. Supports aliases and canonical IDs.
4. **Longest-span resolution** — overlapping gazetteer matches are resolved by keeping the longest span.
5. **Regex pattern extraction** — compiled regex patterns for approval, rejection, escalation, handoff, system entry, reconciliation, change, threshold, exception, validation, and completion phrases.
6. **Entity creation from captures** — regex captures (actor, target, system) that don't match existing gazetteer entities are promoted to entities.
7. **Action classification** — deterministic rule-based classifier maps sentences to action classes.
8. **Relation extraction** — links pattern-captured actors/targets to extracted entities.
9. **Temporal cue detection** — identifies ordering cues (before, after, then, triggered by, etc.).
10. **Control relation building** — links control entities to nearby workflow objects.

### Supported entity types

| Type | Source | Examples |
|---|---|---|
| `PERSON` | Regex capture | Named individuals from pattern matches |
| `ROLE` | Gazetteer + regex | Finance Manager, Clerk, Auditor, CFO |
| `SYSTEM` | Gazetteer + regex | SAP, Oracle, Salesforce, ServiceNow |
| `DEPARTMENT` | Gazetteer | Finance, Legal, IT, Compliance |
| `WORKFLOW_OBJECT` | Gazetteer | Invoice, Purchase Order, Payment, Ticket |
| `ACTION` | Gazetteer | Approve, Reject, Escalate, Submit |
| `CONTROL` | Gazetteer | Approval Control, Reconciliation, SOD, Threshold |
| `POLICY` | Reserved | Not yet populated by deterministic rules |
| `EXCEPTION` | Gazetteer | Error, Discrepancy, Overdue, Policy Breach |
| `CHANGE_EVENT` | Regex | "changed from X to Y", "new control added" |

### Supported relation types

| Relation | Pattern source |
|---|---|
| `approves` | "approved by {role}" |
| `rejects` | "rejected by {role}" |
| `escalates_to` | "escalated to {target}" |
| `creates_in` | "entered/created in {system}" |
| `validates` | "validated by {role}" |
| `executed_in` | System entry patterns |
| `applies_to` | Control → nearest workflow object |
| `changed_from_to` | "changed from X to Y" |
| `handoff_to` | "assigned/sent/forwarded to {target}" |
| `precedes` / `follows` | Temporal cues (before, after, then) |
| `triggered_by` | "triggered by", "once" |
| `conditioned_on` | "conditioned on", "only if" |

### Confidence scoring

Every entity and relation includes a `confidence` (0.0–1.0) and `method` field.

| Method | Baseline confidence |
|---|---|
| Exact gazetteer match | 0.95 |
| Alias match | 0.90 |
| Regex pattern match | 0.85–0.92 |
| Rule-based action classification | 0.78–0.88 |
| Relation (derived from pattern × entity) | base × 0.85 |
| Temporal cue | 0.70–0.80 |

Confidence is not ML-derived. It reflects the signal strength of the matching method.

### Negative and speculative statement handling

Sentences containing negation markers (`not`, `no`, `never`, `has not been`, etc.) or speculative language (`might`, `may`, `could`, `potentially`, `proposed`, `under review`, etc.) are:

1. Excluded from entity and relation extraction.
2. Excluded from action classification.
3. Flagged via `has_negated_content` and `has_speculative_content` on the result.

This prevents "The invoice was not approved" from generating an `APPROVAL` entity.

## Consequences

### Benefits
- Reproducible, auditable extraction with no external dependencies.
- Fast execution (sub-second for typical documents).
- Clear baseline for measuring future LLM extraction improvements.

### Limitations
- **Limited vocabulary** — the gazetteer covers common enterprise process terms but will miss domain-specific terminology.
- **Rigid patterns** — regex patterns handle common phrasings but not paraphrases or complex sentence structures.
- **No coreference resolution** — "he approved it" cannot be linked to a specific role.
- **No cross-sentence reasoning** — relations are extracted within individual sentences.
- **No learning** — the extractor cannot improve from feedback without code changes.

### Future LLM-assisted extraction path

When LLM extraction is introduced:
1. It will run as a separate extraction method (`method: "llm"`).
2. Deterministic extraction results can serve as a prior or validation check.
3. LLM results will validate against the same ProcessIR schema.
4. The `model_invocations` table is already provisioned for tracking LLM calls.
5. Confidence scores from LLM extraction will be calibrated separately.

## References

- `packages/core/process_ir/extractor.py` — main extraction orchestrator
- `packages/core/process_ir/gazetteer.py` — dictionary-based matching
- `packages/core/process_ir/patterns.py` — regex patterns
- `packages/core/process_ir/classifier.py` — action classification
- `packages/core/process_ir/relations.py` — relation extraction
- `packages/core/process_ir/negation.py` — negation/speculative filtering
- `packages/core/process_ir/evaluation.py` — evaluation metrics
- `tests/fixtures/gold_extraction.py` — gold evaluation dataset
