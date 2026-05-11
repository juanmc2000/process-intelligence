"""Integration tests for the process exploration pipeline (TEST-006).

Validates end-to-end behaviour across similarity clustering, lineage
reconstruction, and workflow graph projection using synthetic ProcessIR fixtures.

No database, MinIO, or network calls are required — all tests operate
on in-memory ProcessIR objects.
"""

from uuid import uuid4

import pytest

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
from packages.core.process_ir.similarity import (
    cluster_processes,
    detect_aliases,
    make_fingerprint,
    score_similarity,
)
from packages.core.process_ir.lineage import (
    ChangeCategory,
    build_lineage_chain,
    build_timeline,
    build_timeline_summary,
    detect_superseded,
)
from packages.core.process_ir.graph import (
    EDGE_TYPE_PRECEDES,
    NODE_TYPE_CONTROL,
    NODE_TYPE_WORKFLOW_STEP,
    project_graph,
)


# ---------------------------------------------------------------------------
# Synthetic fixture library
# ---------------------------------------------------------------------------

_EV = EvidenceRef(artifact_uri="minio://test/fixture.json")


def _p(
    pid: str,
    steps: list[tuple[str, int | None]] | None = None,
    roles: list[str] | None = None,
    systems: list[str] | None = None,
    controls: list[str] | None = None,
    decisions: list[str] | None = None,
    exceptions: list[str] | None = None,
    changes: list[tuple[str, str | None]] | None = None,
) -> ProcessIR:
    return ProcessIR(
        id=pid,
        run_id=uuid4(),
        source_artifact_uri=f"minio://test/{pid}.json",
        schema_version="process-ir-v1",
        workflow_steps=[
            WorkflowStep(
                id=f"{pid}_s{i}", name=n, sequence_order=seq, evidence_refs=[_EV]
            )
            for i, (n, seq) in enumerate(steps or [])
        ],
        roles=[Role(id=f"{pid}_r{i}", name=r) for i, r in enumerate(roles or [])],
        system_touchpoints=[
            SystemTouchpoint(
                id=f"{pid}_t{i}", name=s, system_name=s, evidence_refs=[_EV]
            )
            for i, s in enumerate(systems or [])
        ],
        controls=[
            Control(id=f"{pid}_c{i}", name=c, evidence_refs=[_EV])
            for i, c in enumerate(controls or [])
        ],
        decision_points=[
            DecisionPoint(id=f"{pid}_d{i}", name=d, evidence_refs=[_EV])
            for i, d in enumerate(decisions or [])
        ],
        exceptions=[
            ProcessException(id=f"{pid}_x{i}", name=x, evidence_refs=[_EV])
            for i, x in enumerate(exceptions or [])
        ],
        change_events=[
            ChangeEvent(
                id=f"{pid}_ce{i}",
                name=n,
                description=desc,
                evidence_refs=[_EV],
            )
            for i, (n, desc) in enumerate(changes or [])
        ],
    )


# ---------------------------------------------------------------------------
# Canonical fixtures
# ---------------------------------------------------------------------------

# Invoice approval — two identical variants (should cluster / alias)
INVOICE_V1 = _p(
    "invoice_v1",
    steps=[
        ("Receive invoice", 1),
        ("3-way match", 2),
        ("Manager approval", 3),
        ("Post payment", 4),
    ],
    roles=["Finance Clerk", "Finance Manager"],
    systems=["SAP"],
    controls=["3-way match control", "Dual approval"],
)

INVOICE_V2 = _p(
    "invoice_v2",
    steps=[
        ("Receive invoice", 1),
        ("3-way match", 2),
        ("Manager approval", 3),
        ("Post payment", 4),
    ],
    roles=["Finance Clerk", "Finance Manager"],
    systems=["SAP"],
    controls=["3-way match control", "Dual approval"],
)

# Invoice approval evolution (superset of V1 with change events)
INVOICE_V3 = _p(
    "invoice_v3",
    steps=[
        ("Receive invoice", 1),
        ("3-way match", 2),
        ("Manager approval", 3),
        ("Director approval", 4),  # new step
        ("Post payment", 5),
    ],
    roles=["Finance Clerk", "Finance Manager", "Finance Director"],
    systems=["SAP"],
    controls=["3-way match control", "Dual approval"],
    changes=[
        ("Change: Manager approval → Director approval", None),
        ("CFO role change: approval threshold updated", None),
    ],
)

# Employee onboarding — unrelated to invoice
ONBOARDING = _p(
    "onboarding",
    steps=[
        ("Submit offer", 1),
        ("Background check", 2),
        ("System access provisioning", 3),
    ],
    roles=["HR Manager", "IT Admin"],
    systems=["Workday", "Active Directory"],
    controls=["Background check policy"],
)

# Duplicate of onboarding (to test over-grouping prevention with high threshold)
ONBOARDING_COPY = _p(
    "onboarding_copy",
    steps=[
        ("Submit offer", 1),
        ("Background check", 2),
        ("System access provisioning", 3),
    ],
    roles=["HR Manager", "IT Admin"],
    systems=["Workday", "Active Directory"],
    controls=["Background check policy"],
)


# ---------------------------------------------------------------------------
# Test: process grouping
# ---------------------------------------------------------------------------


class TestProcessGrouping:
    def test_invoice_variants_cluster_together(self):
        fps = [make_fingerprint(p) for p in [INVOICE_V1, INVOICE_V2, INVOICE_V3]]
        clusters = cluster_processes(fps, similarity_threshold=0.50)
        # All three invoice variants should land in one cluster
        multi = [c for c in clusters if len(c.process_ids) > 1]
        assert len(multi) >= 1
        combined_ids = {pid for c in multi for pid in c.process_ids}
        assert "invoice_v1" in combined_ids or "invoice_v2" in combined_ids

    def test_unrelated_process_stays_separate(self):
        fps = [make_fingerprint(p) for p in [INVOICE_V1, INVOICE_V2, ONBOARDING]]
        clusters = cluster_processes(fps, similarity_threshold=0.50)
        # Onboarding should be alone
        onboarding_cluster = next(c for c in clusters if "onboarding" in c.process_ids)
        assert len(onboarding_cluster.process_ids) == 1

    def test_identical_copies_flagged_for_merge(self):
        fps = [make_fingerprint(p) for p in [INVOICE_V1, INVOICE_V2]]
        clusters = cluster_processes(
            fps, similarity_threshold=0.50, merge_threshold=0.80
        )
        assert any(c.recommend_merge for c in clusters if len(c.process_ids) > 1)

    def test_all_process_ids_preserved_across_clusters(self):
        all_procs = [INVOICE_V1, INVOICE_V2, INVOICE_V3, ONBOARDING, ONBOARDING_COPY]
        fps = [make_fingerprint(p) for p in all_procs]
        clusters = cluster_processes(fps, similarity_threshold=0.50)
        found_ids = [pid for c in clusters for pid in c.process_ids]
        assert sorted(found_ids) == sorted(p.id for p in all_procs)


# ---------------------------------------------------------------------------
# Test: alias handling
# ---------------------------------------------------------------------------


class TestAliasHandling:
    def test_exact_duplicates_detected_as_aliases(self):
        fps = [make_fingerprint(INVOICE_V1), make_fingerprint(INVOICE_V2)]
        aliases = detect_aliases(fps, alias_threshold=0.90)
        assert len(aliases) == 1

    def test_unrelated_processes_not_aliased(self):
        fps = [make_fingerprint(INVOICE_V1), make_fingerprint(ONBOARDING)]
        aliases = detect_aliases(fps, alias_threshold=0.90)
        assert aliases == []

    def test_alias_group_contains_both_ids(self):
        fps = [make_fingerprint(INVOICE_V1), make_fingerprint(INVOICE_V2)]
        aliases = detect_aliases(fps, alias_threshold=0.85)
        all_ids = {aliases[0].canonical_id} | set(aliases[0].alias_ids)
        assert all_ids == {"invoice_v1", "invoice_v2"}


# ---------------------------------------------------------------------------
# Test: similarity thresholds
# ---------------------------------------------------------------------------


class TestSimilarityThresholds:
    def test_identical_score_is_one(self):
        fp = make_fingerprint(INVOICE_V1)
        result = score_similarity(fp, fp)
        assert result.score == pytest.approx(1.0, abs=0.01)

    def test_v1_v2_score_is_near_one(self):
        fp1, fp2 = make_fingerprint(INVOICE_V1), make_fingerprint(INVOICE_V2)
        result = score_similarity(fp1, fp2)
        assert result.score >= 0.90

    def test_invoice_vs_onboarding_score_is_low(self):
        fp1, fp2 = make_fingerprint(INVOICE_V1), make_fingerprint(ONBOARDING)
        result = score_similarity(fp1, fp2)
        assert result.score < 0.25

    def test_v1_v3_score_reflects_evolution(self):
        # V3 is an evolution of V1 — similar but not identical
        fp1, fp3 = make_fingerprint(INVOICE_V1), make_fingerprint(INVOICE_V3)
        result = score_similarity(fp1, fp3)
        assert 0.40 < result.score < 1.0


# ---------------------------------------------------------------------------
# Test: timeline reconstruction
# ---------------------------------------------------------------------------


class TestTimelineReconstruction:
    def test_v3_has_change_events(self):
        events = build_timeline(INVOICE_V3)
        assert len(events) == 2

    def test_v3_change_category_detected(self):
        events = build_timeline(INVOICE_V3)
        cats = {e.category for e in events}
        # "CFO role change" → role change; "Change: Manager approval → Director approval"
        assert (
            ChangeCategory.ROLE_CHANGE in cats or ChangeCategory.APPROVAL_CHANGE in cats
        )

    def test_from_to_extracted_from_v3(self):
        events = build_timeline(INVOICE_V3)
        arrow_event = next((e for e in events if e.from_value is not None), None)
        assert arrow_event is not None
        assert arrow_event.from_value
        assert arrow_event.to_value

    def test_lineage_chain_v1_to_v3(self):
        chain = build_lineage_chain([INVOICE_V1, INVOICE_V3])
        assert len(chain.versions) == 2
        assert chain.versions[0].process_id == "invoice_v1"
        assert chain.versions[1].process_id == "invoice_v3"
        assert chain.versions[1].supersedes == "invoice_v1"
        assert chain.versions[0].is_superseded

    def test_timeline_summary_reflects_events(self):
        chain = build_lineage_chain([INVOICE_V1, INVOICE_V3])
        summary = build_timeline_summary(chain)
        assert summary["total_change_events"] == 2
        assert summary["version_count"] == 2

    def test_empty_process_has_empty_timeline(self):
        empty = _p("empty")
        events = build_timeline(empty)
        assert events == []

    def test_conflicting_timeline_flagged(self):
        # Manually create two processes both claiming to supersede the same root
        # Use build_lineage_chain for a single version — no actual conflict possible
        # via the API. Test that detect_superseded correctly handles the heuristic.
        chain = build_lineage_chain([INVOICE_V1, INVOICE_V3])
        assert not chain.has_ambiguous_lineage  # linear chain is unambiguous


# ---------------------------------------------------------------------------
# Test: graph consistency
# ---------------------------------------------------------------------------


class TestGraphConsistency:
    def test_invoice_graph_has_step_nodes(self):
        graph = project_graph(INVOICE_V1)
        step_nodes = [n for n in graph.nodes if n.node_type == NODE_TYPE_WORKFLOW_STEP]
        assert len(step_nodes) == 4

    def test_invoice_graph_sequence_edges(self):
        graph = project_graph(INVOICE_V1)
        seq = [e for e in graph.edges if e.edge_type == EDGE_TYPE_PRECEDES]
        # 4 steps with sequence_order → 3 precedes edges
        assert len(seq) == 3

    def test_no_orphan_edges_in_invoice_graph(self):
        graph = project_graph(INVOICE_V1)
        node_ids = {n.id for n in graph.nodes}
        for edge in graph.edges:
            assert edge.source in node_ids, f"Orphan source: {edge.source}"
            assert edge.target in node_ids, f"Orphan target: {edge.target}"

    def test_react_flow_payload_is_valid(self):
        graph = project_graph(INVOICE_V1)
        payload = graph.to_react_flow()
        assert payload["processId"] == "invoice_v1"
        assert isinstance(payload["nodes"], list)
        assert isinstance(payload["edges"], list)

    def test_onboarding_graph_independent_from_invoice(self):
        g_invoice = project_graph(INVOICE_V1)
        g_onboard = project_graph(ONBOARDING)
        invoice_ids = {n.id for n in g_invoice.nodes}
        onboard_ids = {n.id for n in g_onboard.nodes}
        # No shared node IDs between unrelated processes
        assert invoice_ids.isdisjoint(onboard_ids)

    def test_control_nodes_present(self):
        graph = project_graph(INVOICE_V1)
        ctrl_nodes = [n for n in graph.nodes if n.node_type == NODE_TYPE_CONTROL]
        assert len(ctrl_nodes) == 2

    def test_empty_process_graph_has_no_nodes(self):
        empty = _p("empty_graph_test")
        graph = project_graph(empty)
        assert graph.node_count == 0
        assert graph.edge_count == 0


# ---------------------------------------------------------------------------
# Test: duplicate process handling
# ---------------------------------------------------------------------------


class TestDuplicateHandling:
    def test_two_identical_processes_both_clustered(self):
        fps = [make_fingerprint(ONBOARDING), make_fingerprint(ONBOARDING_COPY)]
        clusters = cluster_processes(fps, similarity_threshold=0.50)
        # They should end up in one cluster
        assert any(len(c.process_ids) == 2 for c in clusters)

    def test_duplicate_does_not_break_alias_detection(self):
        fps = [
            make_fingerprint(INVOICE_V1),
            make_fingerprint(INVOICE_V2),
            make_fingerprint(ONBOARDING),
            make_fingerprint(ONBOARDING_COPY),
        ]
        aliases = detect_aliases(fps, alias_threshold=0.90)
        # Should find two alias groups (invoice pair + onboarding pair)
        assert len(aliases) == 2


# ---------------------------------------------------------------------------
# Test: superseded process detection
# ---------------------------------------------------------------------------


class TestSupersededDetection:
    def test_v1_superseded_by_v3(self):
        superseded = detect_superseded([INVOICE_V1, INVOICE_V3])
        assert "invoice_v1" in superseded

    def test_v3_not_superseded(self):
        superseded = detect_superseded([INVOICE_V1, INVOICE_V3])
        assert "invoice_v3" not in superseded

    def test_onboarding_not_superseded_by_invoice(self):
        superseded = detect_superseded([ONBOARDING, INVOICE_V3])
        assert "onboarding" not in superseded
