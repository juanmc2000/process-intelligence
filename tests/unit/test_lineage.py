"""Unit tests for the process lineage and timeline engine (PROCESS-004)."""

from uuid import uuid4


from packages.core.schemas.process_ir import (
    ChangeEvent,
    Control,
    EvidenceRef,
    ProcessIR,
    Role,
    SystemTouchpoint,
    WorkflowStep,
)
from packages.core.process_ir.lineage import (
    ChangeCategory,
    aggregate_changes,
    build_lineage_chain,
    build_timeline,
    build_timeline_summary,
    detect_superseded,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_process(
    pid: str,
    steps: list[str] | None = None,
    roles: list[str] | None = None,
    systems: list[str] | None = None,
    controls: list[str] | None = None,
    changes: list[tuple[str, str | None]] | None = None,
) -> ProcessIR:
    """Build a minimal ProcessIR for testing.

    changes: list of (name, description) tuples.
    """
    run_id = uuid4()
    change_events = [
        ChangeEvent(
            id=f"{pid}_ce{i}",
            name=name,
            description=desc,
            evidence_refs=[EvidenceRef(artifact_uri=f"minio://test/{pid}.json")],
        )
        for i, (name, desc) in enumerate(changes or [])
    ]
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
        change_events=change_events,
    )


# ---------------------------------------------------------------------------
# build_timeline tests
# ---------------------------------------------------------------------------


class TestBuildTimeline:
    def test_empty_process_returns_empty_timeline(self):
        p = _make_process("p1")
        events = build_timeline(p)
        assert events == []

    def test_single_change_event(self):
        p = _make_process(
            "p1", changes=[("Approval limit changed", "increased threshold")]
        )
        events = build_timeline(p)
        assert len(events) == 1
        assert events[0].description == "Approval limit changed"
        assert events[0].process_id == "p1"

    def test_change_categories_classified_correctly(self):
        p = _make_process(
            "p1",
            changes=[
                ("CFO role reassigned", None),
                ("Migrated to SAP system", None),
                ("Approval control updated", None),
                ("General update", None),
            ],
        )
        events = build_timeline(p)
        cats = {e.description: e.category for e in events}
        assert cats["CFO role reassigned"] == ChangeCategory.ROLE_CHANGE
        assert cats["Migrated to SAP system"] == ChangeCategory.SYSTEM_MIGRATION
        assert cats["Approval control updated"] == ChangeCategory.APPROVAL_CHANGE
        assert cats["General update"] == ChangeCategory.GENERAL

    def test_from_to_extraction(self):
        p = _make_process("p1", changes=[("Change: SAP → Oracle", None)])
        events = build_timeline(p)
        assert events[0].from_value == "SAP"
        assert events[0].to_value == "Oracle"

    def test_from_to_absent_when_no_arrow(self):
        p = _make_process("p1", changes=[("System updated", None)])
        events = build_timeline(p)
        assert events[0].from_value is None
        assert events[0].to_value is None

    def test_evidence_refs_preserved(self):
        p = _make_process("p1", changes=[("Some change", None)])
        events = build_timeline(p)
        assert len(events[0].evidence_refs) == 1


# ---------------------------------------------------------------------------
# build_lineage_chain tests
# ---------------------------------------------------------------------------


class TestBuildLineageChain:
    def test_empty_input_returns_empty_chain(self):
        chain = build_lineage_chain([])
        assert chain.versions == []
        assert chain.timeline == []

    def test_single_version_chain(self):
        p = _make_process("p1", steps=["approve"], changes=[("Initial setup", None)])
        chain = build_lineage_chain([p])
        assert len(chain.versions) == 1
        assert chain.versions[0].version_number == 1
        assert chain.versions[0].supersedes is None
        assert not chain.versions[0].is_superseded

    def test_two_version_chain_supersession(self):
        p1 = _make_process("p1", steps=["approve"])
        p2 = _make_process(
            "p2", steps=["approve", "review"], changes=[("Added review step", None)]
        )
        chain = build_lineage_chain([p1, p2])
        assert len(chain.versions) == 2
        assert chain.versions[1].supersedes == "p1"
        assert chain.versions[0].is_superseded
        assert not chain.versions[1].is_superseded

    def test_timeline_spans_all_versions(self):
        p1 = _make_process("p1", changes=[("Change A", None)])
        p2 = _make_process("p2", changes=[("Change B", None), ("Change C", None)])
        chain = build_lineage_chain([p1, p2])
        assert len(chain.timeline) == 3

    def test_version_numbers_assigned_correctly(self):
        p1 = _make_process("p1")
        p2 = _make_process("p2")
        p3 = _make_process("p3")
        chain = build_lineage_chain([p1, p2, p3])
        numbers = [v.version_number for v in chain.versions]
        assert numbers == [1, 2, 3]

    def test_chain_id_derived_from_first_version(self):
        p1 = _make_process("root_process")
        chain = build_lineage_chain([p1])
        assert "root_process" in chain.chain_id

    def test_no_ambiguity_in_simple_linear_chain(self):
        p1 = _make_process("p1")
        p2 = _make_process("p2")
        chain = build_lineage_chain([p1, p2])
        assert not chain.has_ambiguous_lineage

    def test_summary_non_empty(self):
        p1 = _make_process("p1", steps=["step1"])
        p2 = _make_process("p2", steps=["step1", "step2"])
        chain = build_lineage_chain([p1, p2])
        assert chain.summary
        assert "version" in chain.summary.lower()


# ---------------------------------------------------------------------------
# aggregate_changes tests
# ---------------------------------------------------------------------------


class TestAggregateChanges:
    def test_empty_list_returns_empty_categories(self):
        result = aggregate_changes([])
        # All categories present but empty
        assert all(isinstance(v, list) for v in result.values())

    def test_changes_grouped_by_category(self):
        p1 = _make_process("p1", changes=[("CFO role change", None)])
        p2 = _make_process("p2", changes=[("SAP system migration", None)])
        result = aggregate_changes([p1, p2])
        assert len(result[ChangeCategory.ROLE_CHANGE]) == 1
        assert len(result[ChangeCategory.SYSTEM_MIGRATION]) == 1

    def test_all_categories_present_in_result(self):
        result = aggregate_changes([])
        for cat in ChangeCategory:
            assert cat in result

    def test_multiple_changes_same_category(self):
        p1 = _make_process(
            "p1",
            changes=[
                ("CFO role replaced", None),
                ("Owner role reassigned", None),
            ],
        )
        result = aggregate_changes([p1])
        assert len(result[ChangeCategory.ROLE_CHANGE]) == 2


# ---------------------------------------------------------------------------
# detect_superseded tests
# ---------------------------------------------------------------------------


class TestDetectSuperseded:
    def test_empty_list_returns_empty(self):
        assert detect_superseded([]) == []

    def test_single_process_not_superseded(self):
        p = _make_process("p1", steps=["approve"])
        assert detect_superseded([p]) == []

    def test_subset_process_flagged_as_superseded(self):
        # p1 has steps {approve}; p2 has {approve, review} + a change event → p1 is superseded
        p1 = _make_process("p1", steps=["approve"])
        p2 = _make_process(
            "p2", steps=["approve", "review"], changes=[("Added review", None)]
        )
        result = detect_superseded([p1, p2])
        assert "p1" in result

    def test_superset_not_flagged_as_superseded(self):
        p1 = _make_process("p1", steps=["approve"])
        p2 = _make_process(
            "p2", steps=["approve", "review"], changes=[("Added review", None)]
        )
        result = detect_superseded([p1, p2])
        assert "p2" not in result

    def test_disjoint_processes_not_superseded(self):
        p1 = _make_process("p1", steps=["approve", "pay"])
        p2 = _make_process(
            "p2", steps=["hire", "onboard"], changes=[("Changed process", None)]
        )
        result = detect_superseded([p1, p2])
        # p1 steps are not a subset of p2 steps → not superseded
        assert "p1" not in result

    def test_no_change_events_means_no_supersession(self):
        # Even if p2 has a superset of steps, without change_events it doesn't count
        p1 = _make_process("p1", steps=["approve"])
        p2 = _make_process("p2", steps=["approve", "review"])  # no changes
        result = detect_superseded([p1, p2])
        assert result == []


# ---------------------------------------------------------------------------
# build_timeline_summary tests
# ---------------------------------------------------------------------------


class TestBuildTimelineSummary:
    def test_summary_contains_expected_keys(self):
        p1 = _make_process("p1", changes=[("Role changed", None)])
        chain = build_lineage_chain([p1])
        summary = build_timeline_summary(chain)
        assert "chain_id" in summary
        assert "version_count" in summary
        assert "total_change_events" in summary
        assert "change_categories" in summary
        assert "has_ambiguous_lineage" in summary

    def test_summary_counts_correct(self):
        p1 = _make_process("p1", changes=[("Change A", None)])
        p2 = _make_process("p2", changes=[("Change B", None), ("Change C", None)])
        chain = build_lineage_chain([p1, p2])
        summary = build_timeline_summary(chain)
        assert summary["version_count"] == 2
        assert summary["total_change_events"] == 3

    def test_summary_no_raw_content(self):
        p1 = _make_process("p1", changes=[("CONFIDENTIAL: secret change", None)])
        chain = build_lineage_chain([p1])
        summary = build_timeline_summary(chain)
        # Summary dict values should be counts/booleans/strings — not raw evidence text
        assert isinstance(summary["total_change_events"], int)
        assert isinstance(summary["has_ambiguous_lineage"], bool)
