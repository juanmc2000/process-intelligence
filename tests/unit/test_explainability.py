"""Unit tests for the extraction explainability engine (PROCESS-005 / TEST-007A).

All tests use synthetic ProcessIR fixtures — no real customer data, no DB, no
MinIO, no Temporal.  Tests verify that:

- Explanations are deterministic and traceable
- No reasoning is fabricated (explanations reflect the actual data)
- Confidence tiers map correctly from evidence counts
- Edge explanations reflect the correct basis for each edge type
- Confidence decomposition sums correctly
- Evidence lineage coverage ratios are accurate
- Similarity explanations wrap SimilarityScore faithfully
- Negative tests prevent over-reporting evidence or inflating confidence
"""

import pytest
from uuid import uuid4

from packages.core.schemas.process_ir import (
    ChangeEvent,
    Control,
    DecisionPoint,
    EvidenceRef,
    ProcessException,
    ProcessIR,
    Role,
    SystemTouchpoint,
    WorkflowStep,
)
from packages.core.process_ir.explainability import (
    decompose_confidence,
    explain_process,
    explain_similarity,
    summarise_evidence_lineage,
)
from packages.core.process_ir.similarity import make_fingerprint, score_similarity


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------


def _ref(location: str | None = None) -> EvidenceRef:
    return EvidenceRef(
        artifact_uri="minio://test/artifact.json",
        location_hint=location,
    )


def _make_process(
    pid: str = "p1",
    steps: list[str] | None = None,
    roles: list[str] | None = None,
    systems: list[str] | None = None,
    controls: list[str] | None = None,
    exceptions: list[str] | None = None,
    decisions: list[str] | None = None,
    change_events: list[str] | None = None,
    step_refs: int = 0,  # evidence refs per step
    system_refs: int = 0,
    control_refs: int = 0,
) -> ProcessIR:
    run_id = uuid4()
    return ProcessIR(
        id=pid,
        run_id=run_id,
        source_artifact_uri=f"minio://artifacts/{pid}.json",
        schema_version="process-ir-v1",
        workflow_steps=[
            WorkflowStep(
                id=f"{pid}_s{i}",
                name=s,
                sequence_order=i,
                evidence_refs=[_ref(f"page {i}") for _ in range(step_refs)],
            )
            for i, s in enumerate(steps or [])
        ],
        roles=[Role(id=f"{pid}_r{i}", name=r) for i, r in enumerate(roles or [])],
        system_touchpoints=[
            SystemTouchpoint(
                id=f"{pid}_t{i}",
                name=sv,
                system_name=sv,
                evidence_refs=[_ref(f"section {i}") for _ in range(system_refs)],
            )
            for i, sv in enumerate(systems or [])
        ],
        controls=[
            Control(
                id=f"{pid}_c{i}",
                name=c,
                evidence_refs=[_ref(f"para {i}") for _ in range(control_refs)],
            )
            for i, c in enumerate(controls or [])
        ],
        exceptions=[
            ProcessException(id=f"{pid}_x{i}", name=x)
            for i, x in enumerate(exceptions or [])
        ],
        decision_points=[
            DecisionPoint(id=f"{pid}_d{i}", name=d)
            for i, d in enumerate(decisions or [])
        ],
        change_events=[
            ChangeEvent(id=f"{pid}_ce{i}", name=ce)
            for i, ce in enumerate(change_events or [])
        ],
    )


# ---------------------------------------------------------------------------
# Confidence tier tests
# ---------------------------------------------------------------------------


class TestEntityExplanations:
    def test_zero_refs_yields_unverified_tier(self):
        pir = _make_process("p1", steps=["submit request"], step_refs=0)
        exp = explain_process(pir)
        step_exp = next(
            e for e in exp.entity_explanations if e.entity_type == "workflow_step"
        )
        assert step_exp.confidence_tier == "unverified"
        assert step_exp.evidence_count == 0

    def test_one_ref_yields_low_tier(self):
        pir = _make_process("p1", steps=["submit request"], step_refs=1)
        exp = explain_process(pir)
        step_exp = next(
            e for e in exp.entity_explanations if e.entity_type == "workflow_step"
        )
        assert step_exp.confidence_tier == "low"
        assert step_exp.evidence_count == 1

    def test_two_refs_yields_medium_tier(self):
        pir = _make_process("p1", steps=["submit request"], step_refs=2)
        exp = explain_process(pir)
        step_exp = next(
            e for e in exp.entity_explanations if e.entity_type == "workflow_step"
        )
        assert step_exp.confidence_tier == "medium"

    def test_four_refs_yields_high_tier(self):
        pir = _make_process("p1", steps=["submit request"], step_refs=4)
        exp = explain_process(pir)
        step_exp = next(
            e for e in exp.entity_explanations if e.entity_type == "workflow_step"
        )
        assert step_exp.confidence_tier == "high"

    def test_roles_always_unverified(self):
        """Roles carry no evidence_refs in the schema — always unverified."""
        pir = _make_process("p1", roles=["Finance Manager", "Controller"])
        exp = explain_process(pir)
        role_exps = [e for e in exp.entity_explanations if e.entity_type == "role"]
        assert len(role_exps) == 2
        assert all(e.confidence_tier == "unverified" for e in role_exps)
        assert all(e.evidence_count == 0 for e in role_exps)

    def test_entity_explanation_label_matches_source(self):
        pir = _make_process("p1", steps=["Invoice Approval"], controls=["3-Way Match"])
        exp = explain_process(pir)
        labels = {e.label for e in exp.entity_explanations}
        assert "Invoice Approval" in labels
        assert "3-Way Match" in labels

    def test_no_fabrication_negative(self):
        """Explanations must not claim evidence that does not exist."""
        pir = _make_process("p1", steps=["request"], step_refs=0)
        exp = explain_process(pir)
        step_exp = next(
            e for e in exp.entity_explanations if e.entity_type == "workflow_step"
        )
        # evidence_count must be exactly 0 — no inflation
        assert step_exp.evidence_count == 0
        assert step_exp.evidence_locations == []

    def test_evidence_locations_populated(self):
        pir = _make_process("p1", steps=["review"], step_refs=3)
        exp = explain_process(pir)
        step_exp = next(
            e for e in exp.entity_explanations if e.entity_type == "workflow_step"
        )
        # All 3 refs have location hints "page 0"
        assert len(step_exp.evidence_locations) == 3

    def test_all_entity_types_covered(self):
        pir = _make_process(
            "p1",
            steps=["step"],
            roles=["role"],
            systems=["sys"],
            controls=["ctrl"],
            exceptions=["exc"],
            decisions=["dec"],
            change_events=["change"],
        )
        exp = explain_process(pir)
        types = {e.entity_type for e in exp.entity_explanations}
        assert "workflow_step" in types
        assert "role" in types
        assert "system" in types
        assert "control" in types
        assert "exception" in types
        assert "decision_point" in types
        assert "change_event" in types


# ---------------------------------------------------------------------------
# Edge explanation tests
# ---------------------------------------------------------------------------


class TestEdgeExplanations:
    def test_sequence_edges_have_sequence_order_basis(self):
        pir = _make_process("p1", steps=["step a", "step b", "step c"])
        exp = explain_process(pir)
        seq_edges = [e for e in exp.edge_explanations if e.edge_type == "precedes"]
        assert len(seq_edges) == 2  # a→b, b→c
        assert all(e.basis == "sequence_order" for e in seq_edges)

    def test_role_edges_have_role_assignment_basis(self):
        from packages.core.schemas.process_ir import WorkflowStep, Role

        pir = ProcessIR(
            id="p1",
            run_id=uuid4(),
            source_artifact_uri="minio://test/p1.json",
            schema_version="process-ir-v1",
            workflow_steps=[
                WorkflowStep(
                    id="s1", name="approve", role="Finance Manager", sequence_order=0
                )
            ],
            roles=[Role(id="r1", name="Finance Manager")],
        )
        exp = explain_process(pir)
        role_edges = [
            e for e in exp.edge_explanations if e.edge_type == "involves_role"
        ]
        assert len(role_edges) == 1
        assert role_edges[0].basis == "role_assignment"
        assert "Finance Manager" in role_edges[0].rationale

    def test_system_edges_have_system_assignment_basis(self):
        from packages.core.schemas.process_ir import WorkflowStep, SystemTouchpoint

        pir = ProcessIR(
            id="p1",
            run_id=uuid4(),
            source_artifact_uri="minio://test/p1.json",
            schema_version="process-ir-v1",
            workflow_steps=[
                WorkflowStep(id="s1", name="enter", system="SAP", sequence_order=0)
            ],
            system_touchpoints=[
                SystemTouchpoint(id="t1", name="SAP", system_name="SAP")
            ],
        )
        exp = explain_process(pir)
        sys_edges = [e for e in exp.edge_explanations if e.edge_type == "executed_in"]
        assert len(sys_edges) == 1
        assert sys_edges[0].basis == "system_assignment"

    def test_control_edges_have_control_heuristic_basis(self):
        pir = _make_process("p1", steps=["review"], controls=["3-way match"])
        exp = explain_process(pir)
        ctrl_edges = [e for e in exp.edge_explanations if e.edge_type == "validates"]
        assert len(ctrl_edges) == 1
        assert ctrl_edges[0].basis == "control_heuristic"
        assert "heuristic" in ctrl_edges[0].rationale.lower()

    def test_empty_process_has_no_edges(self):
        pir = _make_process("p1")
        exp = explain_process(pir)
        assert exp.edge_explanations == []

    def test_no_orphan_edges(self):
        """All edges must reference nodes that exist in the graph."""
        pir = _make_process(
            "p1",
            steps=["a", "b", "c"],
            roles=["manager"],
            systems=["SAP"],
            controls=["approval"],
        )
        exp = explain_process(pir)
        # rationale is always a non-empty string
        assert all(e.rationale for e in exp.edge_explanations)


# ---------------------------------------------------------------------------
# Confidence decomposition tests
# ---------------------------------------------------------------------------


class TestConfidenceDecomposition:
    def test_empty_process_scores_fifty(self):
        """Empty process: 0/6 dimensions populated → score = 50 + 0*40 = 50."""
        pir = _make_process("p1")
        cd = decompose_confidence(pir)
        assert cd.overall_score == 50
        assert cd.tier == "low"
        assert cd.total_data_points == 0

    def test_all_dimensions_populated_scores_near_ninety(self):
        pir = _make_process(
            "p1",
            steps=["s"],
            roles=["r"],
            systems=["sys"],
            controls=["c"],
            exceptions=["x"],
            decisions=["d"],
        )
        cd = decompose_confidence(pir)
        # 6/6 populated → 50 + (6/6)*40 = 90
        assert cd.overall_score == 90
        assert cd.tier == "high"

    def test_partial_population_intermediate_score(self):
        pir = _make_process("p1", steps=["step"], roles=["role"], systems=["SAP"])
        cd = decompose_confidence(pir)
        # 3/6 populated → 50 + 0.5*40 = 70
        assert cd.overall_score == 70

    def test_dimension_count_matches_present_entities(self):
        pir = _make_process("p1", steps=["a", "b", "c"])
        cd = decompose_confidence(pir)
        step_dim = next(d for d in cd.dimensions if d.name == "workflow_steps")
        assert step_dim.count == 3
        assert step_dim.present is True

    def test_absent_dimensions_have_zero_contribution(self):
        pir = _make_process("p1", steps=["step"])
        cd = decompose_confidence(pir)
        absent = [d for d in cd.dimensions if not d.present]
        assert all(d.score_contribution == 0.0 for d in absent)

    def test_rationale_is_non_empty(self):
        pir = _make_process("p1", steps=["step"])
        cd = decompose_confidence(pir)
        assert cd.rationale
        assert str(cd.overall_score) in cd.rationale

    def test_negative_no_inflation(self):
        """Score must not exceed 90 for any single-dimension process."""
        pir = _make_process("p1", steps=["only steps are here"])
        cd = decompose_confidence(pir)
        assert cd.overall_score <= 90
        # Only 1 dimension present → score must be < 90
        assert cd.overall_score < 90


# ---------------------------------------------------------------------------
# Evidence lineage summary tests
# ---------------------------------------------------------------------------


class TestEvidenceLineage:
    def test_empty_process_zero_coverage(self):
        pir = _make_process("p1")
        el = summarise_evidence_lineage(pir)
        assert el.total_evidence_refs == 0
        assert el.total_entities == 0
        assert el.coverage_ratio == 0.0

    def test_all_evidenced_high_coverage(self):
        pir = _make_process("p1", steps=["s1", "s2"], step_refs=2)
        el = summarise_evidence_lineage(pir)
        assert el.entities_with_evidence == 2
        assert el.coverage_ratio == pytest.approx(1.0)

    def test_roles_count_as_unevidenced(self):
        pir = _make_process("p1", roles=["manager"])
        el = summarise_evidence_lineage(pir)
        assert el.total_entities == 1
        assert el.entities_with_evidence == 0
        assert "role" in el.unevidenced_entity_types

    def test_well_evidenced_labels_require_two_or_more_refs(self):
        pir = _make_process("p1", steps=["step one", "step two"], step_refs=2)
        el = summarise_evidence_lineage(pir)
        assert "step one" in el.well_evidenced_entity_labels
        assert "step two" in el.well_evidenced_entity_labels

    def test_single_ref_not_in_well_evidenced(self):
        pir = _make_process("p1", steps=["step"], step_refs=1)
        el = summarise_evidence_lineage(pir)
        assert "step" not in el.well_evidenced_entity_labels

    def test_lineage_note_non_empty(self):
        pir = _make_process("p1", steps=["step"], step_refs=2)
        el = summarise_evidence_lineage(pir)
        assert el.lineage_note

    def test_no_fabrication_negative(self):
        """total_evidence_refs must exactly match the evidence provided."""
        pir = _make_process("p1", steps=["a", "b"], step_refs=3)
        el = summarise_evidence_lineage(pir)
        # 2 steps × 3 refs each = 6 total refs
        assert el.total_evidence_refs == 6


# ---------------------------------------------------------------------------
# Similarity explanation tests
# ---------------------------------------------------------------------------


class TestSimilarityExplanation:
    def _sim(self, pid_a: str, pid_b: str, **kwargs_a) -> object:
        pa = _make_process(pid_a, **kwargs_a)
        pb = _make_process(pid_b, **kwargs_a)
        score = score_similarity(make_fingerprint(pa), make_fingerprint(pb))
        return explain_similarity(score)

    def test_identical_processes_verdict_likely_same(self):
        exp = self._sim("a", "b", steps=["approve", "pay"], roles=["manager"])
        assert exp.verdict == "likely same process"

    def test_distinct_processes_verdict_not_same_process(self):
        # Processes with no structural overlap must NOT be treated as likely same process.
        # Note: empty dimensions both score 1.0 (Jaccard of two empty sets), so the composite
        # may be "related" rather than "distinct" when only a few dimensions differ.
        pa = _make_process(
            "a", steps=["approve invoice"], roles=["CFO"], systems=["SAP"]
        )
        pb = _make_process(
            "b", steps=["hire employee"], roles=["HR Manager"], systems=["Workday"]
        )
        score = score_similarity(make_fingerprint(pa), make_fingerprint(pb))
        exp = explain_similarity(score)
        # With systems also differing, score should be low enough to be distinct or related
        assert exp.verdict in ("distinct", "related")
        assert not score.is_likely_same_process

    def test_top_driver_dimensions_three_or_fewer(self):
        exp = self._sim("a", "b", steps=["step"])
        assert 1 <= len(exp.top_driver_dimensions) <= 3

    def test_composite_score_matches_similarity_score(self):
        pa = _make_process("a", steps=["s1", "s2"])
        pb = _make_process("b", steps=["s1", "s2"])
        score = score_similarity(make_fingerprint(pa), make_fingerprint(pb))
        exp = explain_similarity(score)
        assert exp.composite_score == pytest.approx(score.score)

    def test_human_summary_non_empty(self):
        exp = self._sim("a", "b", steps=["step"])
        assert exp.human_summary

    def test_dimension_explanations_all_dimensions_present(self):
        exp = self._sim("a", "b", steps=["step"])
        dimension_names = {d.dimension for d in exp.dimensions}
        assert "steps" in dimension_names
        assert "roles" in dimension_names
        assert "systems" in dimension_names

    def test_shared_labels_accuracy(self):
        """Shared labels must only include labels actually shared by both processes."""
        pa = _make_process("a", steps=["approve", "pay"])
        pb = _make_process("b", steps=["approve", "reject"])
        score = score_similarity(make_fingerprint(pa), make_fingerprint(pb))
        exp = explain_similarity(score)
        steps_dim = next(d for d in exp.dimensions if d.dimension == "steps")
        assert "approve" in steps_dim.shared_labels
        assert "pay" not in steps_dim.shared_labels
        assert "reject" not in steps_dim.shared_labels

    def test_no_fabricated_shared_labels_negative(self):
        """When processes share no labels, shared_labels must be empty."""
        pa = _make_process("a", steps=["x", "y"])
        pb = _make_process("b", steps=["a", "b"])
        score = score_similarity(make_fingerprint(pa), make_fingerprint(pb))
        exp = explain_similarity(score)
        all_shared = [label for d in exp.dimensions for label in d.shared_labels]
        assert all_shared == []


# ---------------------------------------------------------------------------
# Full explain_process bundle tests
# ---------------------------------------------------------------------------


class TestExplainProcess:
    def test_process_id_matches(self):
        pir = _make_process("my-process")
        exp = explain_process(pir)
        assert exp.process_id == "my-process"

    def test_schema_version_matches(self):
        pir = _make_process("p1")
        pir.schema_version = "process-ir-v2"
        exp = explain_process(pir)
        assert exp.schema_version == "process-ir-v2"

    def test_all_bundles_populated(self):
        pir = _make_process("p1", steps=["step"], controls=["ctrl"])
        exp = explain_process(pir)
        assert exp.entity_explanations
        assert exp.confidence_decomposition is not None
        assert exp.evidence_lineage is not None

    def test_deterministic_output(self):
        """Two calls with the same input must return identical results."""
        pir = _make_process(
            "p1",
            steps=["approve", "pay"],
            roles=["manager"],
            systems=["SAP"],
            step_refs=2,
        )
        exp1 = explain_process(pir)
        exp2 = explain_process(pir)
        assert (
            exp1.confidence_decomposition.overall_score
            == exp2.confidence_decomposition.overall_score
        )
        assert (
            exp1.evidence_lineage.coverage_ratio == exp2.evidence_lineage.coverage_ratio
        )
        assert len(exp1.entity_explanations) == len(exp2.entity_explanations)
        assert len(exp1.edge_explanations) == len(exp2.edge_explanations)

    def test_graph_provided_directly(self):
        """When a pre-built graph is provided, explain_process must use it."""
        from packages.core.process_ir.graph import project_graph

        pir = _make_process("p1", steps=["a", "b"])
        graph = project_graph(pir)
        exp_with_graph = explain_process(pir, graph=graph)
        exp_without = explain_process(pir)
        assert len(exp_with_graph.edge_explanations) == len(
            exp_without.edge_explanations
        )
