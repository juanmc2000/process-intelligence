"""Extraction explainability engine.

Provides deterministic, traceable explanations for:
- ProcessIR entity presence (evidence lineage, confidence tier)
- Workflow graph edge existence (basis and rationale)
- Similarity scoring (per-dimension drivers and shared labels)
- Confidence decomposition (weighted per-dimension breakdown)
- Evidence lineage summaries (coverage ratio, well/unevidenced entities)

All explanations are fully deterministic — no LLM calls, no fabrication.
Confidence tiers and rationales are derived from evidence counts and
structural facts already present in ProcessIR and the graph projection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from packages.core.process_ir.graph import (
    EDGE_TYPE_EXECUTED_IN,
    EDGE_TYPE_INVOLVES_ROLE,
    EDGE_TYPE_PRECEDES,
    EDGE_TYPE_VALIDATES,
    WorkflowGraph,
)
from packages.core.process_ir.similarity import (
    SimilarityScore,
    _WEIGHTS,
)  # noqa: PLC2701
from packages.core.schemas.process_ir import ProcessIR


# ---------------------------------------------------------------------------
# Confidence tier helpers
# ---------------------------------------------------------------------------

# Thresholds for deriving a confidence tier from an evidence count.
# 0 refs = "unverified"; 1 = "low"; 2-3 = "medium"; 4+ = "high".
_EVIDENCE_TIERS: list[tuple[int, str]] = [
    (4, "high"),
    (2, "medium"),
    (1, "low"),
    (0, "unverified"),
]


def _evidence_tier(count: int) -> str:
    for threshold, tier in _EVIDENCE_TIERS:
        if count >= threshold:
            return tier
    return "unverified"


def _evidence_rationale(count: int, entity_type: str) -> str:
    tier = _evidence_tier(count)
    if tier == "high":
        return f"Supported by {count} evidence references — high extraction confidence."
    if tier == "medium":
        return f"Supported by {count} evidence reference(s) — moderate confidence."
    if tier == "low":
        return "Supported by a single evidence reference — review recommended."
    return (
        f"{entity_type.replace('_', ' ').capitalize()} has no direct evidence references. "
        "May be inferred from context."
    )


# ---------------------------------------------------------------------------
# Entity explanations
# ---------------------------------------------------------------------------


@dataclass
class EntityExplanation:
    """Explanation for the presence and confidence of a single ProcessIR entity."""

    entity_id: str
    entity_type: str  # e.g. "workflow_step", "role", "system", "control"
    label: str
    evidence_count: int
    evidence_locations: list[str]  # location_hint values from evidence_refs
    confidence_tier: str  # "high" | "medium" | "low" | "unverified"
    rationale: str


def _explain_entity(
    entity_id: str,
    entity_type: str,
    label: str,
    evidence_refs: list,
) -> EntityExplanation:
    """Build an EntityExplanation from raw entity fields."""
    locations = [ref.location_hint for ref in evidence_refs if ref.location_hint]
    count = len(evidence_refs)
    return EntityExplanation(
        entity_id=entity_id,
        entity_type=entity_type,
        label=label,
        evidence_count=count,
        evidence_locations=locations,
        confidence_tier=_evidence_tier(count),
        rationale=_evidence_rationale(count, entity_type),
    )


def _entity_explanations_from_process_ir(
    process_ir: ProcessIR,
) -> list[EntityExplanation]:
    """Extract EntityExplanations for all entity types in a ProcessIR."""
    explanations: list[EntityExplanation] = []

    for step in process_ir.workflow_steps:
        explanations.append(
            _explain_entity(step.id, "workflow_step", step.name, step.evidence_refs)
        )

    # Roles carry no evidence_refs in the current schema — always unverified.
    for role in process_ir.roles:
        explanations.append(
            EntityExplanation(
                entity_id=role.id,
                entity_type="role",
                label=role.name,
                evidence_count=0,
                evidence_locations=[],
                confidence_tier="unverified",
                rationale=(
                    "Roles are inferred from step assignments and text patterns. "
                    "No direct evidence references are stored."
                ),
            )
        )

    for tp in process_ir.system_touchpoints:
        explanations.append(
            _explain_entity(tp.id, "system", tp.system_name, tp.evidence_refs)
        )

    for ctrl in process_ir.controls:
        explanations.append(
            _explain_entity(ctrl.id, "control", ctrl.name, ctrl.evidence_refs)
        )

    for dp in process_ir.decision_points:
        explanations.append(
            _explain_entity(dp.id, "decision_point", dp.name, dp.evidence_refs)
        )

    for exc in process_ir.exceptions:
        explanations.append(
            _explain_entity(exc.id, "exception", exc.name, exc.evidence_refs)
        )

    for ce in process_ir.change_events:
        explanations.append(
            _explain_entity(ce.id, "change_event", ce.name, ce.evidence_refs)
        )

    return explanations


# ---------------------------------------------------------------------------
# Edge explanations
# ---------------------------------------------------------------------------

# Human-readable descriptions for each edge basis.
_EDGE_BASIS_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    # edge_type: (basis label, rationale template)
    EDGE_TYPE_PRECEDES: (
        "sequence_order",
        "Sequence edge: {src} precedes {tgt} based on assigned sequence_order values.",
    ),
    EDGE_TYPE_INVOLVES_ROLE: (
        "role_assignment",
        "Role edge: {src} is performed by role {tgt}, derived from step.role attribute.",
    ),
    EDGE_TYPE_EXECUTED_IN: (
        "system_assignment",
        "System edge: {src} is executed in system {tgt}, derived from step.system attribute.",
    ),
    EDGE_TYPE_VALIDATES: (
        "control_heuristic",
        (
            "Control edge: {src} validates {tgt}. "
            "Connected by positional heuristic — no explicit step-to-control relation extracted."
        ),
    ),
}


@dataclass
class EdgeExplanation:
    """Explanation for the existence of a single workflow graph edge."""

    edge_id: str
    edge_type: str
    source_label: str
    target_label: str
    basis: str  # "sequence_order" | "role_assignment" | "system_assignment" | "control_heuristic"
    rationale: str


def _explain_edges(graph: WorkflowGraph) -> list[EdgeExplanation]:
    """Build EdgeExplanations for all edges in a WorkflowGraph."""
    node_labels: dict[str, str] = {n.id: n.label for n in graph.nodes}
    explanations: list[EdgeExplanation] = []

    for edge in graph.edges:
        src_label = node_labels.get(edge.source, edge.source)
        tgt_label = node_labels.get(edge.target, edge.target)

        if edge.edge_type in _EDGE_BASIS_DESCRIPTIONS:
            basis, template = _EDGE_BASIS_DESCRIPTIONS[edge.edge_type]
            rationale = template.format(src=src_label, tgt=tgt_label)
        else:
            basis = "inferred"
            rationale = (
                f"Edge from {src_label} to {tgt_label} (type: {edge.edge_type}) "
                "was generated by an unspecified inference rule."
            )

        explanations.append(
            EdgeExplanation(
                edge_id=edge.id,
                edge_type=edge.edge_type,
                source_label=src_label,
                target_label=tgt_label,
                basis=basis,
                rationale=rationale,
            )
        )

    return explanations


# ---------------------------------------------------------------------------
# Confidence decomposition
# ---------------------------------------------------------------------------

# Per-dimension weights for the overall confidence score.
# Mirrors the formula used by the UI: 50 + (populated/total * 40).
# Explicitly defined here for traceability and testing.
_CONFIDENCE_DIMENSIONS: list[tuple[str, str, float]] = [
    # (attribute_name, display_name, weight)
    ("workflow_steps", "Workflow steps", 0.40),
    ("roles", "Roles", 0.20),
    ("system_touchpoints", "System touchpoints", 0.20),
    ("controls", "Controls", 0.10),
    ("exceptions", "Exceptions", 0.05),
    ("decision_points", "Decision points", 0.05),
]


@dataclass
class ConfidenceDimension:
    """Confidence contribution for a single structural dimension."""

    name: str
    display_name: str
    count: int
    weight: float
    # Contribution to overall score: weight * (1 if count > 0 else 0) * 40
    score_contribution: float
    present: bool
    description: str


@dataclass
class ConfidenceDecomposition:
    """Full confidence decomposition for a ProcessIR instance."""

    process_id: str
    overall_score: int  # 0-100, same formula as UI
    tier: str  # "high" | "medium" | "low"
    total_data_points: int
    dimensions: list[ConfidenceDimension]
    rationale: str


def _confidence_tier_label(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 58:
        return "medium"
    return "low"


def decompose_confidence(process_ir: ProcessIR) -> ConfidenceDecomposition:
    """Decompose the overall confidence score into per-dimension contributions.

    The overall score is computed with the same formula as the frontend UI:
        score = 50 + (populated_dimensions / total_dimensions) * 40

    This function surfaces exactly which dimensions are populated, their
    individual counts, and how much each contributes to the final score.
    """
    attr_map = {
        "workflow_steps": process_ir.workflow_steps,
        "roles": process_ir.roles,
        "system_touchpoints": process_ir.system_touchpoints,
        "controls": process_ir.controls,
        "exceptions": process_ir.exceptions,
        "decision_points": process_ir.decision_points,
    }

    populated = sum(1 for lst in attr_map.values() if lst)
    total = len(attr_map)
    overall = round(50 + (populated / total) * 40)
    tier = _confidence_tier_label(overall)
    total_data_points = sum(len(lst) for lst in attr_map.values())

    dims: list[ConfidenceDimension] = []
    for attr, display_name, weight in _CONFIDENCE_DIMENSIONS:
        items = attr_map[attr]
        count = len(items)
        present = count > 0
        # Each present dimension contributes (weight / total_weight) * 40 to the variable portion.
        # total_weight = sum of weights for present dims; simplify: uniform contribution per dim.
        contribution = round((1 / total) * 40, 4) if present else 0.0

        if present:
            desc = (
                f"{count} {display_name.lower()} extracted — contributes to confidence."
            )
        else:
            desc = f"No {display_name.lower()} extracted — reduces confidence."

        dims.append(
            ConfidenceDimension(
                name=attr,
                display_name=display_name,
                count=count,
                weight=weight,
                score_contribution=contribution,
                present=present,
                description=desc,
            )
        )

    # Build narrative rationale
    present_names = [d.display_name for d in dims if d.present]
    absent_names = [d.display_name for d in dims if not d.present]
    rationale_parts = [f"Overall confidence: {overall}% ({tier})."]
    if present_names:
        rationale_parts.append(f"Populated: {', '.join(present_names)}.")
    if absent_names:
        rationale_parts.append(f"Missing: {', '.join(absent_names)}.")
    rationale = " ".join(rationale_parts)

    return ConfidenceDecomposition(
        process_id=process_ir.id,
        overall_score=overall,
        tier=tier,
        total_data_points=total_data_points,
        dimensions=dims,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Evidence lineage summary
# ---------------------------------------------------------------------------


@dataclass
class EvidenceLineageSummary:
    """Summary of evidence coverage across all entities in a ProcessIR."""

    process_id: str
    total_evidence_refs: int
    entities_with_evidence: int
    total_entities: int
    coverage_ratio: float  # entities_with_evidence / total_entities (0–1)
    well_evidenced_entity_labels: list[str]  # labels with 2+ evidence refs
    unevidenced_entity_types: list[str]  # entity types with zero refs
    lineage_note: str


def summarise_evidence_lineage(process_ir: ProcessIR) -> EvidenceLineageSummary:
    """Build an evidence lineage summary for a ProcessIR instance.

    Counts evidence refs per entity type, identifies well-evidenced entities
    (2+ refs), and flags entity types with no evidence at all.
    """
    # Collect (label, ref_count, entity_type) for all entities that carry refs.
    entity_data: list[tuple[str, int, str]] = []

    for step in process_ir.workflow_steps:
        entity_data.append((step.name, len(step.evidence_refs), "workflow_step"))
    for tp in process_ir.system_touchpoints:
        entity_data.append((tp.system_name, len(tp.evidence_refs), "system"))
    for ctrl in process_ir.controls:
        entity_data.append((ctrl.name, len(ctrl.evidence_refs), "control"))
    for dp in process_ir.decision_points:
        entity_data.append((dp.name, len(dp.evidence_refs), "decision_point"))
    for exc in process_ir.exceptions:
        entity_data.append((exc.name, len(exc.evidence_refs), "exception"))
    for ce in process_ir.change_events:
        entity_data.append((ce.name, len(ce.evidence_refs), "change_event"))
    # Roles have no evidence_refs — treated as unevidenced if present.
    for role in process_ir.roles:
        entity_data.append((role.name, 0, "role"))

    total = len(entity_data)
    with_evidence = sum(1 for _, count, _ in entity_data if count > 0)
    total_refs = sum(count for _, count, _ in entity_data)
    coverage = round(with_evidence / total, 4) if total > 0 else 0.0

    well_evidenced = sorted({label for label, count, _ in entity_data if count >= 2})

    # Entity types where every instance has zero refs
    types_with_items: dict[str, int] = {}
    types_with_any_ref: set[str] = set()
    for _, count, etype in entity_data:
        types_with_items[etype] = types_with_items.get(etype, 0) + 1
        if count > 0:
            types_with_any_ref.add(etype)
    unevidenced_types = sorted(
        etype for etype in types_with_items if etype not in types_with_any_ref
    )

    # Build lineage note
    if total == 0:
        note = "No entities found in this ProcessIR."
    elif coverage >= 0.80:
        note = (
            f"{with_evidence}/{total} entities have at least one evidence reference "
            f"({round(coverage * 100)}% coverage). Evidence lineage is strong."
        )
    elif coverage >= 0.50:
        note = (
            f"{with_evidence}/{total} entities have evidence references "
            f"({round(coverage * 100)}% coverage). Some entities lack direct evidence."
        )
    else:
        note = (
            f"Only {with_evidence}/{total} entities have evidence references "
            f"({round(coverage * 100)}% coverage). Evidence lineage is sparse — review recommended."
        )

    return EvidenceLineageSummary(
        process_id=process_ir.id,
        total_evidence_refs=total_refs,
        entities_with_evidence=with_evidence,
        total_entities=total,
        coverage_ratio=coverage,
        well_evidenced_entity_labels=well_evidenced,
        unevidenced_entity_types=unevidenced_types,
        lineage_note=note,
    )


# ---------------------------------------------------------------------------
# Similarity explanation
# ---------------------------------------------------------------------------


@dataclass
class DimensionExplanation:
    """Per-dimension explanation within a similarity score."""

    dimension: str
    score: float
    weight: float
    weighted_contribution: float
    overlap_count: int
    shared_labels: list[str]
    description: str


@dataclass
class SimilarityExplanation:
    """Rich explanation for a pairwise similarity score between two processes."""

    process_id_a: str
    process_id_b: str
    composite_score: float
    verdict: str  # "likely same process" | "possible alias" | "related" | "distinct"
    dimensions: list[DimensionExplanation]
    top_driver_dimensions: list[str]  # top-3 dimensions by score
    human_summary: str


def _similarity_verdict(score: SimilarityScore) -> str:
    if score.is_likely_same_process:
        return "likely same process"
    if score.is_likely_alias:
        return "possible alias"
    if score.score >= 0.40:
        return "related"
    return "distinct"


def explain_similarity(score: SimilarityScore) -> SimilarityExplanation:
    """Build a rich SimilarityExplanation from a SimilarityScore.

    Enriches each dimension with its weight, weighted contribution, and a
    human-readable description of what drove the score.
    """
    dim_explanations: list[DimensionExplanation] = []

    for ds in score.dimensions:
        weight = _WEIGHTS.get(ds.dimension, 0.0)
        contribution = round(ds.score * weight, 4)

        if ds.score >= 0.80:
            desc = f"Strong {ds.dimension} overlap ({ds.score:.0%})."
        elif ds.score >= 0.50:
            desc = f"Partial {ds.dimension} overlap ({ds.score:.0%})."
        elif ds.score > 0:
            desc = f"Weak {ds.dimension} overlap ({ds.score:.0%})."
        else:
            desc = f"No {ds.dimension} overlap."

        if ds.overlap:
            desc += f" Shared: {', '.join(ds.overlap[:3])}."

        dim_explanations.append(
            DimensionExplanation(
                dimension=ds.dimension,
                score=ds.score,
                weight=weight,
                weighted_contribution=contribution,
                overlap_count=len(ds.overlap),
                shared_labels=ds.overlap,
                description=desc,
            )
        )

    # Top 3 driver dimensions by score
    top_dims = sorted(dim_explanations, key=lambda d: d.score, reverse=True)
    top_driver_names = [d.dimension for d in top_dims[:3]]

    verdict = _similarity_verdict(score)

    # Build human summary
    top_desc = ", ".join(f"{d.dimension} ({d.score:.0%})" for d in top_dims[:3])
    summary = (
        f"Composite similarity: {score.score:.2f} — {verdict}. "
        f"Top drivers: {top_desc}."
    )
    all_shared = [label for d in dim_explanations for label in d.shared_labels[:2]]
    if all_shared:
        summary += (
            f" Shared labels include: {', '.join(dict.fromkeys(all_shared[:5]))}."
        )

    return SimilarityExplanation(
        process_id_a=score.process_id_a,
        process_id_b=score.process_id_b,
        composite_score=score.score,
        verdict=verdict,
        dimensions=dim_explanations,
        top_driver_dimensions=top_driver_names,
        human_summary=summary,
    )


# ---------------------------------------------------------------------------
# Full process explanation bundle
# ---------------------------------------------------------------------------


@dataclass
class ProcessExplanation:
    """Complete explainability bundle for a ProcessIR instance.

    Combines entity, edge, confidence, and evidence lineage explanations
    into a single serialisable structure for API consumption.
    """

    process_id: str
    schema_version: str
    entity_explanations: list[EntityExplanation] = field(default_factory=list)
    edge_explanations: list[EdgeExplanation] = field(default_factory=list)
    confidence_decomposition: Optional[ConfidenceDecomposition] = None
    evidence_lineage: Optional[EvidenceLineageSummary] = None


def explain_process(
    process_ir: ProcessIR,
    graph: Optional[WorkflowGraph] = None,
) -> ProcessExplanation:
    """Build a full explainability bundle for a ProcessIR instance.

    Args:
        process_ir: The ProcessIR to explain.
        graph: Optional pre-computed WorkflowGraph. If not supplied, the
               graph is projected internally to generate edge explanations.

    Returns:
        ProcessExplanation containing entity, edge, confidence, and lineage
        explanations derived purely from the ProcessIR data.
    """
    from packages.core.process_ir.graph import project_graph

    if graph is None:
        graph = project_graph(process_ir)

    return ProcessExplanation(
        process_id=process_ir.id,
        schema_version=process_ir.schema_version,
        entity_explanations=_entity_explanations_from_process_ir(process_ir),
        edge_explanations=_explain_edges(graph),
        confidence_decomposition=decompose_confidence(process_ir),
        evidence_lineage=summarise_evidence_lineage(process_ir),
    )
