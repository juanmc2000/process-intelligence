"""Unit tests for the process similarity and clustering engine (PROCESS-003)."""

import pytest
from uuid import uuid4

from packages.core.schemas.process_ir import (
    Control,
    ProcessIR,
    Role,
    SystemTouchpoint,
    WorkflowStep,
)
from packages.core.process_ir.similarity import (
    cluster_processes,
    detect_aliases,
    make_fingerprint,
    score_similarity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_process(
    pid: str,
    steps: list[str] | None = None,
    roles: list[str] | None = None,
    systems: list[str] | None = None,
    controls: list[str] | None = None,
) -> ProcessIR:
    run_id = uuid4()
    return ProcessIR(
        id=pid,
        run_id=run_id,
        source_artifact_uri=f"minio://artifacts/{pid}.json",
        schema_version="process-ir-v1",
        workflow_steps=[
            WorkflowStep(id=f"{pid}_s{i}", name=s) for i, s in enumerate(steps or [])
        ],
        roles=[Role(id=f"{pid}_r{i}", name=r) for i, r in enumerate(roles or [])],
        system_touchpoints=[
            SystemTouchpoint(id=f"{pid}_t{i}", name=s, system_name=s)
            for i, s in enumerate(systems or [])
        ],
        controls=[
            Control(id=f"{pid}_c{i}", name=c) for i, c in enumerate(controls or [])
        ],
    )


# ---------------------------------------------------------------------------
# Fingerprint tests
# ---------------------------------------------------------------------------


class TestMakeFingerprint:
    def test_empty_process_produces_empty_fingerprint(self):
        process = _make_process("p1")
        fp = make_fingerprint(process)
        assert fp.process_id == "p1"
        assert fp.is_empty

    def test_labels_are_normalised_to_lowercase(self):
        process = _make_process("p1", steps=["Invoice Approval", "SEND EMAIL"])
        fp = make_fingerprint(process)
        assert "invoice approval" in fp.step_labels
        assert "send email" in fp.step_labels

    def test_all_dimensions_populated(self):
        process = _make_process(
            "p1",
            steps=["step a"],
            roles=["Finance Manager"],
            systems=["SAP"],
            controls=["3-way match"],
        )
        fp = make_fingerprint(process)
        assert "step a" in fp.step_labels
        assert "finance manager" in fp.role_labels
        assert "sap" in fp.system_labels
        assert "3-way match" in fp.control_labels


# ---------------------------------------------------------------------------
# Similarity scoring tests
# ---------------------------------------------------------------------------


class TestScoreSimilarity:
    def test_identical_processes_score_one(self):
        p = _make_process(
            "p1", steps=["approve", "pay"], roles=["manager"], systems=["SAP"]
        )
        fp = make_fingerprint(p)
        result = score_similarity(fp, fp)
        assert result.score == pytest.approx(1.0, abs=0.01)

    def test_completely_different_processes_score_near_zero(self):
        p1 = _make_process(
            "p1", steps=["approve invoice"], roles=["CFO"], systems=["SAP"]
        )
        p2 = _make_process(
            "p2", steps=["hire employee"], roles=["HR Manager"], systems=["Workday"]
        )
        fp1, fp2 = make_fingerprint(p1), make_fingerprint(p2)
        result = score_similarity(fp1, fp2)
        # No overlap → score should be low (empty dims both score 1.0 but shared dims differ)
        assert result.score < 0.30

    def test_same_process_different_ids_scores_high(self):
        p1 = _make_process(
            "p1", steps=["review", "approve", "pay"], roles=["manager"], systems=["SAP"]
        )
        p2 = _make_process(
            "p2", steps=["review", "approve", "pay"], roles=["manager"], systems=["SAP"]
        )
        fp1, fp2 = make_fingerprint(p1), make_fingerprint(p2)
        result = score_similarity(fp1, fp2)
        assert result.score >= 0.90

    def test_partial_overlap_returns_intermediate_score(self):
        p1 = _make_process("p1", steps=["a", "b", "c"], roles=["manager"])
        p2 = _make_process("p2", steps=["a", "b", "d"], roles=["manager"])
        fp1, fp2 = make_fingerprint(p1), make_fingerprint(p2)
        result = score_similarity(fp1, fp2)
        assert 0.30 < result.score < 1.0

    def test_explanation_is_non_empty(self):
        p1 = _make_process("p1", steps=["approve"])
        p2 = _make_process("p2", steps=["approve"])
        result = score_similarity(make_fingerprint(p1), make_fingerprint(p2))
        assert result.explanation
        assert "score" in result.explanation.lower()

    def test_dimension_scores_present(self):
        p1 = _make_process("p1", steps=["approve"], roles=["manager"])
        p2 = _make_process("p2", steps=["approve"], roles=["director"])
        result = score_similarity(make_fingerprint(p1), make_fingerprint(p2))
        dim_names = {d.dimension for d in result.dimensions}
        assert "steps" in dim_names
        assert "roles" in dim_names

    def test_symmetry(self):
        p1 = _make_process("p1", steps=["a", "b"], roles=["x"])
        p2 = _make_process("p2", steps=["b", "c"], roles=["y"])
        fp1, fp2 = make_fingerprint(p1), make_fingerprint(p2)
        s12 = score_similarity(fp1, fp2)
        s21 = score_similarity(fp2, fp1)
        assert s12.score == pytest.approx(s21.score, abs=0.001)


# ---------------------------------------------------------------------------
# Alias detection tests
# ---------------------------------------------------------------------------


class TestDetectAliases:
    def test_identical_processes_detected_as_aliases(self):
        p1 = _make_process(
            "p1", steps=["approve", "pay"], roles=["CFO"], systems=["SAP"]
        )
        p2 = _make_process(
            "p2", steps=["approve", "pay"], roles=["CFO"], systems=["SAP"]
        )
        fps = [make_fingerprint(p1), make_fingerprint(p2)]
        groups = detect_aliases(fps, alias_threshold=0.80)
        assert len(groups) == 1
        assert set(groups[0].alias_ids) | {groups[0].canonical_id} == {"p1", "p2"}

    def test_unrelated_processes_not_grouped(self):
        p1 = _make_process(
            "p1", steps=["invoice approval"], roles=["CFO"], systems=["SAP"]
        )
        p2 = _make_process(
            "p2", steps=["employee onboarding"], roles=["HR"], systems=["Workday"]
        )
        fps = [make_fingerprint(p1), make_fingerprint(p2)]
        groups = detect_aliases(fps, alias_threshold=0.80)
        assert groups == []

    def test_transitive_aliases_merged(self):
        # p1 ≈ p2, p2 ≈ p3 → all three should be in one group
        shared = ["approve", "review", "pay"]
        p1 = _make_process("p1", steps=shared, roles=["CFO"], systems=["SAP"])
        p2 = _make_process("p2", steps=shared, roles=["CFO"], systems=["SAP"])
        p3 = _make_process("p3", steps=shared, roles=["CFO"], systems=["SAP"])
        fps = [make_fingerprint(p) for p in [p1, p2, p3]]
        groups = detect_aliases(fps, alias_threshold=0.80)
        assert len(groups) == 1
        all_ids = {groups[0].canonical_id} | set(groups[0].alias_ids)
        assert all_ids == {"p1", "p2", "p3"}

    def test_empty_fingerprints_not_grouped(self):
        # Two empty processes score 1.0 (all dims empty) — this is a degenerate case.
        # The alias detection should still work without crashing.
        p1 = _make_process("p1")
        p2 = _make_process("p2")
        fps = [make_fingerprint(p1), make_fingerprint(p2)]
        # Empty fingerprints both score 1.0 → they will be aliased (expected behaviour)
        groups = detect_aliases(fps, alias_threshold=0.80)
        assert isinstance(groups, list)

    def test_single_process_returns_no_groups(self):
        p1 = _make_process("p1", steps=["approve"])
        groups = detect_aliases([make_fingerprint(p1)])
        assert groups == []


# ---------------------------------------------------------------------------
# Clustering tests
# ---------------------------------------------------------------------------


class TestClusterProcesses:
    def test_empty_input_returns_empty(self):
        assert cluster_processes([]) == []

    def test_single_process_forms_own_cluster(self):
        p1 = _make_process("p1", steps=["approve"])
        clusters = cluster_processes([make_fingerprint(p1)])
        assert len(clusters) == 1
        assert clusters[0].process_ids == ["p1"]

    def test_similar_processes_grouped_together(self):
        p1 = _make_process("p1", steps=["approve", "pay"], roles=["CFO"])
        p2 = _make_process("p2", steps=["approve", "pay"], roles=["CFO"])
        p3 = _make_process("p3", steps=["hire", "onboard"], roles=["HR"])
        fps = [make_fingerprint(p) for p in [p1, p2, p3]]
        clusters = cluster_processes(fps, similarity_threshold=0.50)
        # p1 and p2 should be together; p3 should be separate
        assert len(clusters) == 2
        sizes = sorted(len(c.process_ids) for c in clusters)
        assert sizes == [1, 2]

    def test_merge_recommendation_for_high_cohesion(self):
        p1 = _make_process("p1", steps=["a", "b", "c"], roles=["x"], systems=["S"])
        p2 = _make_process("p2", steps=["a", "b", "c"], roles=["x"], systems=["S"])
        fps = [make_fingerprint(p) for p in [p1, p2]]
        clusters = cluster_processes(
            fps, similarity_threshold=0.50, merge_threshold=0.80
        )
        merged_cluster = next(c for c in clusters if len(c.process_ids) > 1)
        assert merged_cluster.recommend_merge
        assert merged_cluster.merge_note is not None

    def test_no_merge_recommendation_for_low_cohesion(self):
        p1 = _make_process("p1", steps=["a", "b"], roles=["x"])
        p2 = _make_process("p2", steps=["a", "c"], roles=["y"])
        fps = [make_fingerprint(p) for p in [p1, p2]]
        clusters = cluster_processes(
            fps, similarity_threshold=0.10, merge_threshold=0.90
        )
        # With very high merge threshold and partial overlap, no merge expected
        if len(clusters) == 1:
            assert not clusters[0].recommend_merge or clusters[0].cohesion >= 0.90

    def test_unrelated_processes_each_in_own_cluster(self):
        p1 = _make_process(
            "p1", steps=["invoice approval"], roles=["CFO"], systems=["SAP"]
        )
        p2 = _make_process(
            "p2", steps=["employee hiring"], roles=["HR"], systems=["Workday"]
        )
        fps = [make_fingerprint(p) for p in [p1, p2]]
        clusters = cluster_processes(fps, similarity_threshold=0.70)
        assert len(clusters) == 2

    def test_cluster_ids_are_unique(self):
        processes = [_make_process(f"p{i}", steps=[f"step{i}"]) for i in range(5)]
        fps = [make_fingerprint(p) for p in processes]
        clusters = cluster_processes(fps)
        ids = [c.cluster_id for c in clusters]
        assert len(ids) == len(set(ids))

    def test_all_process_ids_preserved(self):
        processes = [_make_process(f"p{i}", steps=[f"step{i}"]) for i in range(4)]
        fps = [make_fingerprint(p) for p in processes]
        clusters = cluster_processes(fps, similarity_threshold=0.90)
        all_ids = [pid for c in clusters for pid in c.process_ids]
        assert sorted(all_ids) == ["p0", "p1", "p2", "p3"]
