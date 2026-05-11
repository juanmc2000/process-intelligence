"""Unit tests for the workflow graph projection layer (GRAPH-001)."""

from uuid import uuid4

from packages.core.schemas.process_ir import (
    Control,
    DecisionPoint,
    EvidenceRef,
    ProcessException,
    ProcessIR,
    Role,
    SystemTouchpoint,
    WorkflowStep,
)
from packages.core.process_ir.graph import (
    EDGE_TYPE_EXECUTED_IN,
    EDGE_TYPE_INVOLVES_ROLE,
    EDGE_TYPE_PRECEDES,
    EDGE_TYPE_VALIDATES,
    NODE_TYPE_CONTROL,
    NODE_TYPE_DECISION,
    NODE_TYPE_EXCEPTION,
    NODE_TYPE_ROLE,
    NODE_TYPE_SYSTEM,
    NODE_TYPE_WORKFLOW_STEP,
    project_graph,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_process(
    pid: str,
    steps: list[tuple[str, int | None, str | None, str | None]] | None = None,
    roles: list[str] | None = None,
    systems: list[str] | None = None,
    controls: list[str] | None = None,
    decisions: list[str] | None = None,
    exceptions: list[str] | None = None,
) -> ProcessIR:
    """Build a ProcessIR for testing.

    steps: list of (name, sequence_order, role_name, system_name).
    """
    ev = EvidenceRef(artifact_uri=f"minio://test/{pid}.json")
    return ProcessIR(
        id=pid,
        run_id=uuid4(),
        source_artifact_uri=f"minio://artifacts/{pid}.json",
        schema_version="process-ir-v1",
        workflow_steps=[
            WorkflowStep(
                id=f"{pid}_s{i}",
                name=name,
                sequence_order=seq,
                role=role_name,
                system=sys_name,
                evidence_refs=[ev],
            )
            for i, (name, seq, role_name, sys_name) in enumerate(steps or [])
        ],
        roles=[Role(id=f"{pid}_r{i}", name=r) for i, r in enumerate(roles or [])],
        system_touchpoints=[
            SystemTouchpoint(
                id=f"{pid}_t{i}", name=s, system_name=s, evidence_refs=[ev]
            )
            for i, s in enumerate(systems or [])
        ],
        controls=[
            Control(id=f"{pid}_c{i}", name=c, evidence_refs=[ev])
            for i, c in enumerate(controls or [])
        ],
        decision_points=[
            DecisionPoint(id=f"{pid}_d{i}", name=d, evidence_refs=[ev])
            for i, d in enumerate(decisions or [])
        ],
        exceptions=[
            ProcessException(id=f"{pid}_x{i}", name=x, evidence_refs=[ev])
            for i, x in enumerate(exceptions or [])
        ],
    )


# ---------------------------------------------------------------------------
# Node generation tests
# ---------------------------------------------------------------------------


class TestNodeGeneration:
    def test_empty_process_produces_no_nodes(self):
        p = _make_process("p1")
        graph = project_graph(p)
        assert graph.node_count == 0

    def test_workflow_step_nodes_generated(self):
        p = _make_process("p1", steps=[("Approve Invoice", None, None, None)])
        graph = project_graph(p)
        types = [n.node_type for n in graph.nodes]
        assert NODE_TYPE_WORKFLOW_STEP in types

    def test_role_nodes_generated(self):
        p = _make_process("p1", roles=["Finance Manager"])
        graph = project_graph(p)
        types = [n.node_type for n in graph.nodes]
        assert NODE_TYPE_ROLE in types

    def test_system_nodes_generated(self):
        p = _make_process("p1", systems=["SAP"])
        graph = project_graph(p)
        types = [n.node_type for n in graph.nodes]
        assert NODE_TYPE_SYSTEM in types

    def test_control_nodes_generated(self):
        p = _make_process("p1", controls=["3-way match"])
        graph = project_graph(p)
        types = [n.node_type for n in graph.nodes]
        assert NODE_TYPE_CONTROL in types

    def test_decision_nodes_generated(self):
        p = _make_process("p1", decisions=["Approve or Reject?"])
        graph = project_graph(p)
        types = [n.node_type for n in graph.nodes]
        assert NODE_TYPE_DECISION in types

    def test_exception_nodes_generated(self):
        p = _make_process("p1", exceptions=["Duplicate invoice"])
        graph = project_graph(p)
        types = [n.node_type for n in graph.nodes]
        assert NODE_TYPE_EXCEPTION in types

    def test_node_ids_match_process_ir_ids(self):
        p = _make_process(
            "p1",
            steps=[("Approve", None, None, None)],
            roles=["CFO"],
        )
        graph = project_graph(p)
        node_ids = {n.id for n in graph.nodes}
        assert "p1_s0" in node_ids
        assert "p1_r0" in node_ids

    def test_node_labels_match_process_ir_names(self):
        p = _make_process("p1", steps=[("Review Document", None, None, None)])
        graph = project_graph(p)
        labels = [n.label for n in graph.nodes]
        assert "Review Document" in labels

    def test_all_node_ids_are_unique(self):
        p = _make_process(
            "p1",
            steps=[("a", None, None, None), ("b", None, None, None)],
            roles=["x", "y"],
            systems=["SAP"],
        )
        graph = project_graph(p)
        ids = [n.id for n in graph.nodes]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Edge generation tests
# ---------------------------------------------------------------------------


class TestEdgeGeneration:
    def test_sequence_edges_created_for_ordered_steps(self):
        p = _make_process(
            "p1",
            steps=[
                ("Step A", 1, None, None),
                ("Step B", 2, None, None),
                ("Step C", 3, None, None),
            ],
        )
        graph = project_graph(p)
        seq_edges = [e for e in graph.edges if e.edge_type == EDGE_TYPE_PRECEDES]
        assert len(seq_edges) == 2

    def test_no_sequence_edges_without_sequence_order(self):
        p = _make_process(
            "p1",
            steps=[("A", None, None, None), ("B", None, None, None)],
        )
        graph = project_graph(p)
        seq_edges = [e for e in graph.edges if e.edge_type == EDGE_TYPE_PRECEDES]
        assert len(seq_edges) == 0

    def test_role_edge_created_when_step_has_role(self):
        p = _make_process(
            "p1",
            steps=[("Approve", None, "CFO", None)],
            roles=["CFO"],
        )
        graph = project_graph(p)
        role_edges = [e for e in graph.edges if e.edge_type == EDGE_TYPE_INVOLVES_ROLE]
        assert len(role_edges) == 1

    def test_system_edge_created_when_step_has_system(self):
        p = _make_process(
            "p1",
            steps=[("Enter data", None, None, "SAP")],
            systems=["SAP"],
        )
        graph = project_graph(p)
        sys_edges = [e for e in graph.edges if e.edge_type == EDGE_TYPE_EXECUTED_IN]
        assert len(sys_edges) == 1

    def test_control_edge_created_when_control_and_step_present(self):
        p = _make_process(
            "p1",
            steps=[("Approve", None, None, None)],
            controls=["3-way match"],
        )
        graph = project_graph(p)
        ctrl_edges = [e for e in graph.edges if e.edge_type == EDGE_TYPE_VALIDATES]
        assert len(ctrl_edges) == 1

    def test_no_orphan_edges(self):
        """All edges must reference nodes that exist in the graph."""
        p = _make_process(
            "p1",
            steps=[("Approve", 1, "CFO", "SAP"), ("Pay", 2, None, None)],
            roles=["CFO"],
            systems=["SAP"],
            controls=["Reconciliation"],
        )
        graph = project_graph(p)
        node_ids = {n.id for n in graph.nodes}
        for edge in graph.edges:
            assert edge.source in node_ids, f"Source {edge.source} not in nodes"
            assert edge.target in node_ids, f"Target {edge.target} not in nodes"

    def test_all_edge_ids_are_unique(self):
        p = _make_process(
            "p1",
            steps=[("A", 1, "CFO", "SAP"), ("B", 2, None, None)],
            roles=["CFO"],
            systems=["SAP"],
            controls=["ctrl"],
        )
        graph = project_graph(p)
        ids = [e.id for e in graph.edges]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# React Flow serialisation tests
# ---------------------------------------------------------------------------


class TestReactFlowSerialisation:
    def test_to_react_flow_returns_dict(self):
        p = _make_process("p1", steps=[("Approve", None, None, None)])
        graph = project_graph(p)
        payload = graph.to_react_flow()
        assert isinstance(payload, dict)

    def test_react_flow_payload_has_required_keys(self):
        p = _make_process("p1")
        graph = project_graph(p)
        payload = graph.to_react_flow()
        assert "nodes" in payload
        assert "edges" in payload
        assert "metadata" in payload
        assert "processId" in payload

    def test_react_flow_nodes_have_required_fields(self):
        p = _make_process("p1", steps=[("Approve", None, None, None)])
        graph = project_graph(p)
        payload = graph.to_react_flow()
        for node in payload["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "data" in node
            assert "label" in node["data"]
            assert "position" in node

    def test_react_flow_edges_have_required_fields(self):
        p = _make_process(
            "p1",
            steps=[("A", 1, None, None), ("B", 2, None, None)],
        )
        graph = project_graph(p)
        payload = graph.to_react_flow()
        for edge in payload["edges"]:
            assert "id" in edge
            assert "source" in edge
            assert "target" in edge
            assert "type" in edge

    def test_process_id_preserved_in_payload(self):
        p = _make_process("my-unique-process-id")
        graph = project_graph(p)
        payload = graph.to_react_flow()
        assert payload["processId"] == "my-unique-process-id"


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_metadata_contains_counts(self):
        p = _make_process(
            "p1",
            steps=[("A", None, None, None), ("B", None, None, None)],
            roles=["CFO"],
        )
        graph = project_graph(p)
        assert graph.metadata["node_count"] == 3
        assert graph.metadata["edge_count"] == graph.edge_count

    def test_metadata_node_type_counts(self):
        p = _make_process("p1", steps=[("A", None, None, None)], roles=["CFO"])
        graph = project_graph(p)
        type_counts = graph.metadata["node_type_counts"]
        assert type_counts[NODE_TYPE_WORKFLOW_STEP] == 1
        assert type_counts[NODE_TYPE_ROLE] == 1

    def test_position_hints_assigned_to_all_nodes(self):
        p = _make_process(
            "p1",
            steps=[("A", None, None, None)],
            roles=["CFO"],
            systems=["SAP"],
        )
        graph = project_graph(p)
        for node in graph.nodes:
            assert node.position_hint is not None
            assert "x" in node.position_hint
            assert "y" in node.position_hint
