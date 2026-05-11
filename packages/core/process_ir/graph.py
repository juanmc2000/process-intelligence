"""Workflow graph projection layer.

Converts a ProcessIR instance into a React Flow-compatible graph payload
suitable for frontend visualization.

All logic is stateless and purely algorithmic — no database, API, storage,
or LLM dependencies.  Entity/relation IDs from the source ProcessIR are
preserved in the output so the frontend can link back to the review workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from packages.core.schemas.process_ir import ProcessIR


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------

# React Flow node type constants.
NODE_TYPE_WORKFLOW_STEP = "workflow_step"
NODE_TYPE_ROLE = "role"
NODE_TYPE_SYSTEM = "system"
NODE_TYPE_CONTROL = "control"
NODE_TYPE_DECISION = "decision"
NODE_TYPE_EXCEPTION = "exception"
NODE_TYPE_HANDOFF = "handoff"

# Edge type constants (mirror relation types from ExtractedRelation).
EDGE_TYPE_PRECEDES = "precedes"
EDGE_TYPE_EXECUTED_IN = "executed_in"
EDGE_TYPE_APPROVED_BY = "approved_by"
EDGE_TYPE_HANDOFF_TO = "handoff_to"
EDGE_TYPE_VALIDATES = "validates"
EDGE_TYPE_CONDITIONED_ON = "conditioned_on"
EDGE_TYPE_INVOLVES_ROLE = "involves_role"
EDGE_TYPE_INVOLVES_SYSTEM = "involves_system"


# ---------------------------------------------------------------------------
# Graph node / edge dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A React Flow-compatible graph node."""

    id: str
    node_type: str  # one of the NODE_TYPE_* constants
    label: str
    # Optional extra data surfaced in the metadata panel
    data: dict[str, Any] = field(default_factory=dict)
    # Layout position hint (column / row for DAG layout)
    position_hint: Optional[dict[str, int]] = None

    def to_react_flow(self) -> dict[str, Any]:
        """Serialise to a React Flow node dict."""
        return {
            "id": self.id,
            "type": self.node_type,
            "data": {
                "label": self.label,
                **self.data,
            },
            "position": self.position_hint or {"x": 0, "y": 0},
        }


@dataclass
class GraphEdge:
    """A React Flow-compatible graph edge."""

    id: str
    source: str  # source node id
    target: str  # target node id
    edge_type: str  # one of the EDGE_TYPE_* constants
    label: Optional[str] = None
    animated: bool = False

    def to_react_flow(self) -> dict[str, Any]:
        """Serialise to a React Flow edge dict."""
        payload: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.edge_type,
            "animated": self.animated,
        }
        if self.label:
            payload["label"] = self.label
        return payload


# ---------------------------------------------------------------------------
# Graph projection result
# ---------------------------------------------------------------------------


@dataclass
class WorkflowGraph:
    """The complete graph projection for a ProcessIR instance."""

    process_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    # Metadata for the graph panel header
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_react_flow(self) -> dict[str, Any]:
        """Serialise the full graph to a React Flow-compatible payload."""
        return {
            "processId": self.process_id,
            "nodes": [n.to_react_flow() for n in self.nodes],
            "edges": [e.to_react_flow() for e in self.edges],
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _assign_positions(nodes: list[GraphNode]) -> None:
    """Assign simple DAG-style x/y position hints to nodes.

    Groups nodes by type into columns, then spaces them vertically within
    each column.  This gives the frontend a reasonable starting layout
    without requiring a full graph-layout algorithm.

    Column order (left → right): roles → workflow_steps → systems/controls/decisions
    Exception and handoff nodes go in the rightmost column.
    """
    column_order = [
        NODE_TYPE_ROLE,
        NODE_TYPE_WORKFLOW_STEP,
        NODE_TYPE_DECISION,
        NODE_TYPE_SYSTEM,
        NODE_TYPE_CONTROL,
        NODE_TYPE_EXCEPTION,
        NODE_TYPE_HANDOFF,
    ]
    col_x = {t: i * 220 for i, t in enumerate(column_order)}
    col_counts: dict[str, int] = {}

    for node in nodes:
        col = col_x.get(node.node_type, len(column_order) * 220)
        row = col_counts.get(node.node_type, 0)
        col_counts[node.node_type] = row + 1
        node.position_hint = {"x": col, "y": row * 120}


# ---------------------------------------------------------------------------
# Node builders
# ---------------------------------------------------------------------------


def _workflow_step_nodes(process_ir: ProcessIR) -> list[GraphNode]:
    nodes = []
    for i, step in enumerate(process_ir.workflow_steps):
        nodes.append(
            GraphNode(
                id=step.id,
                node_type=NODE_TYPE_WORKFLOW_STEP,
                label=step.name,
                data={
                    "description": step.description,
                    "role": step.role,
                    "system": step.system,
                    "sequence_order": step.sequence_order,
                    "evidence_count": len(step.evidence_refs),
                },
            )
        )
    return nodes


def _role_nodes(process_ir: ProcessIR) -> list[GraphNode]:
    return [
        GraphNode(
            id=r.id,
            node_type=NODE_TYPE_ROLE,
            label=r.name,
            data={"description": r.description},
        )
        for r in process_ir.roles
    ]


def _system_nodes(process_ir: ProcessIR) -> list[GraphNode]:
    return [
        GraphNode(
            id=t.id,
            node_type=NODE_TYPE_SYSTEM,
            label=t.system_name,
            data={
                "interaction_type": t.interaction_type,
                "evidence_count": len(t.evidence_refs),
            },
        )
        for t in process_ir.system_touchpoints
    ]


def _control_nodes(process_ir: ProcessIR) -> list[GraphNode]:
    return [
        GraphNode(
            id=c.id,
            node_type=NODE_TYPE_CONTROL,
            label=c.name,
            data={
                "control_type": c.control_type,
                "description": c.description,
                "evidence_count": len(c.evidence_refs),
            },
        )
        for c in process_ir.controls
    ]


def _decision_nodes(process_ir: ProcessIR) -> list[GraphNode]:
    return [
        GraphNode(
            id=d.id,
            node_type=NODE_TYPE_DECISION,
            label=d.name,
            data={
                "conditions": d.conditions,
                "outcomes": d.outcomes,
                "evidence_count": len(d.evidence_refs),
            },
        )
        for d in process_ir.decision_points
    ]


def _exception_nodes(process_ir: ProcessIR) -> list[GraphNode]:
    return [
        GraphNode(
            id=x.id,
            node_type=NODE_TYPE_EXCEPTION,
            label=x.name,
            data={
                "description": x.description,
                "handling_steps": x.handling_steps,
                "evidence_count": len(x.evidence_refs),
            },
        )
        for x in process_ir.exceptions
    ]


# ---------------------------------------------------------------------------
# Edge builders
# ---------------------------------------------------------------------------


def _sequence_edges(process_ir: ProcessIR) -> list[GraphEdge]:
    """Create 'precedes' edges between workflow steps with sequence_order set."""
    ordered = sorted(
        [s for s in process_ir.workflow_steps if s.sequence_order is not None],
        key=lambda s: s.sequence_order,  # type: ignore[arg-type]
    )
    edges = []
    for i in range(len(ordered) - 1):
        src, tgt = ordered[i], ordered[i + 1]
        edges.append(
            GraphEdge(
                id=f"edge_seq_{src.id}_{tgt.id}",
                source=src.id,
                target=tgt.id,
                edge_type=EDGE_TYPE_PRECEDES,
                label="precedes",
            )
        )
    return edges


def _role_edges(process_ir: ProcessIR) -> list[GraphEdge]:
    """Create edges from workflow steps to roles when step.role is set."""
    role_map = {r.name.lower(): r.id for r in process_ir.roles}
    edges = []
    for step in process_ir.workflow_steps:
        if step.role:
            role_id = role_map.get(step.role.lower())
            if role_id:
                edges.append(
                    GraphEdge(
                        id=f"edge_role_{step.id}_{role_id}",
                        source=step.id,
                        target=role_id,
                        edge_type=EDGE_TYPE_INVOLVES_ROLE,
                        label="performed by",
                    )
                )
    return edges


def _system_edges(process_ir: ProcessIR) -> list[GraphEdge]:
    """Create edges from workflow steps to systems when step.system is set."""
    system_map = {t.system_name.lower(): t.id for t in process_ir.system_touchpoints}
    edges = []
    for step in process_ir.workflow_steps:
        if step.system:
            sys_id = system_map.get(step.system.lower())
            if sys_id:
                edges.append(
                    GraphEdge(
                        id=f"edge_sys_{step.id}_{sys_id}",
                        source=step.id,
                        target=sys_id,
                        edge_type=EDGE_TYPE_EXECUTED_IN,
                        label="executed in",
                    )
                )
    return edges


def _control_edges(process_ir: ProcessIR) -> list[GraphEdge]:
    """Connect each control node to the first workflow step (position-based heuristic).

    A control 'validates' the overall process flow; without explicit step-to-control
    relation data, we connect each control to the nearest workflow step by index.
    This is a layout heuristic — a future improvement would use extracted relations.
    """
    if not process_ir.workflow_steps or not process_ir.controls:
        return []
    edges = []
    for i, ctrl in enumerate(process_ir.controls):
        # Attach to workflow step at the same index, or the last step
        step = process_ir.workflow_steps[min(i, len(process_ir.workflow_steps) - 1)]
        edges.append(
            GraphEdge(
                id=f"edge_ctrl_{ctrl.id}_{step.id}",
                source=ctrl.id,
                target=step.id,
                edge_type=EDGE_TYPE_VALIDATES,
                label="validates",
                animated=True,
            )
        )
    return edges


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def project_graph(process_ir: ProcessIR) -> WorkflowGraph:
    """Project a ProcessIR into a React Flow-compatible WorkflowGraph.

    Builds nodes for all ProcessIR entity types and edges for sequence,
    role, system, and control relationships.  Position hints are assigned
    using a column-based DAG layout.

    Args:
        process_ir: The ProcessIR instance to project.

    Returns:
        WorkflowGraph with nodes, edges, and React Flow-compatible serialisation.
    """
    nodes: list[GraphNode] = []
    nodes.extend(_workflow_step_nodes(process_ir))
    nodes.extend(_role_nodes(process_ir))
    nodes.extend(_system_nodes(process_ir))
    nodes.extend(_control_nodes(process_ir))
    nodes.extend(_decision_nodes(process_ir))
    nodes.extend(_exception_nodes(process_ir))

    edges: list[GraphEdge] = []
    edges.extend(_sequence_edges(process_ir))
    edges.extend(_role_edges(process_ir))
    edges.extend(_system_edges(process_ir))
    edges.extend(_control_edges(process_ir))

    _assign_positions(nodes)

    # Remove edges that reference non-existent node IDs (orphan guard)
    node_ids = {n.id for n in nodes}
    edges = [e for e in edges if e.source in node_ids and e.target in node_ids]

    metadata = _build_metadata(process_ir, nodes, edges)

    return WorkflowGraph(
        process_id=process_ir.id,
        nodes=nodes,
        edges=edges,
        metadata=metadata,
    )


def _build_metadata(
    process_ir: ProcessIR,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> dict[str, Any]:
    """Build the metadata dict for the graph panel header."""
    type_counts: dict[str, int] = {}
    for n in nodes:
        type_counts[n.node_type] = type_counts.get(n.node_type, 0) + 1

    return {
        "process_id": process_ir.id,
        "schema_version": process_ir.schema_version,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_type_counts": type_counts,
    }
