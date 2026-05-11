"""Process exploration endpoints.

Routes:
  GET /processes              — list all completed extraction results (process candidates)
  GET /processes/groups       — list similarity-based process groups
  GET /processes/{id}         — retrieve structured metadata for a single process
  GET /processes/{id}/timeline — retrieve change timeline for a process
  GET /processes/{id}/graph   — retrieve React Flow workflow graph for a process

All endpoints return structured ProcessIR-derived data only.
No raw customer content is exposed.
"""

import json
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from packages.core.database.repository import (
    get_extraction_result_by_id,
    list_extraction_results,
)
from packages.core.database.session import get_connection
from packages.core.process_ir.graph import project_graph
from packages.core.process_ir.lineage import build_timeline, build_timeline_summary
from packages.core.process_ir.similarity import (
    cluster_processes,
    make_fingerprint,
)
from packages.core.schemas.process_ir import ProcessIR

router = APIRouter(prefix="/processes", tags=["processes"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ProcessSummaryResponse(BaseModel):
    """Lightweight summary of a single process candidate."""

    extraction_result_id: UUID
    extraction_run_id: UUID
    run_id: UUID
    extraction_status: str
    process_ir_uri: Optional[str] = None
    schema_version: Optional[str] = None
    filename: Optional[str] = None
    created_at: Any


class ProcessDetailResponse(BaseModel):
    """Full structured ProcessIR for a single process candidate.

    Returns only structured process facts — no raw customer content.
    """

    extraction_result_id: UUID
    run_id: UUID
    schema_version: Optional[str] = None
    process_ir: Optional[dict[str, Any]] = None
    confidence_summary: Optional[dict[str, Any]] = None


class TimelineResponse(BaseModel):
    """Timeline and lineage summary for a process."""

    extraction_result_id: UUID
    process_id: Optional[str] = None
    events: list[dict[str, Any]]
    summary: dict[str, Any]


class GraphResponse(BaseModel):
    """React Flow-compatible workflow graph for a process."""

    extraction_result_id: UUID
    graph: dict[str, Any]


class ProcessGroupMember(BaseModel):
    process_id: str
    extraction_result_id: Optional[str] = None


class ProcessGroupResponse(BaseModel):
    """A cluster of similar process candidates."""

    cluster_id: str
    process_ids: list[str]
    cohesion: float
    recommend_merge: bool
    merge_note: Optional[str] = None


class ProcessGroupsResponse(BaseModel):
    """Full similarity grouping result."""

    groups: list[ProcessGroupResponse]
    singleton_count: int  # groups with only one process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _download_process_ir(process_ir_uri: str) -> Optional[dict[str, Any]]:
    """Download ProcessIR JSON from MinIO.  Returns None on any error."""
    from packages.core.storage.client import make_storage_client
    from packages.core.storage.operations import download_bytes, parse_object_uri

    try:
        bucket, key = parse_object_uri(process_ir_uri)
        storage = make_storage_client()
        data = download_bytes(storage, bucket, key)
        return json.loads(data)
    except Exception:
        return None


def _build_confidence_summary(process_ir: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_step_count": len(process_ir.get("workflow_steps", [])),
        "decision_point_count": len(process_ir.get("decision_points", [])),
        "system_touchpoint_count": len(process_ir.get("system_touchpoints", [])),
        "role_count": len(process_ir.get("roles", [])),
        "control_count": len(process_ir.get("controls", [])),
        "exception_count": len(process_ir.get("exceptions", [])),
        "change_event_count": len(process_ir.get("change_events", [])),
    }


def _parse_process_ir(data: dict[str, Any]) -> Optional[ProcessIR]:
    """Deserialise a ProcessIR dict into a typed ProcessIR object."""
    try:
        return ProcessIR.model_validate(data)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ProcessSummaryResponse])
def list_processes(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ProcessSummaryResponse]:
    """List all completed process extraction results (process candidates).

    Returns structured metadata only — no raw customer content.
    """
    with get_connection() as conn:
        rows = list_extraction_results(conn, limit=limit, offset=offset)

    return [
        ProcessSummaryResponse(
            extraction_result_id=row["extraction_result_id"],
            extraction_run_id=row["extraction_run_id"],
            run_id=row["run_id"],
            extraction_status=row["extraction_status"],
            process_ir_uri=row.get("process_ir_uri"),
            schema_version=row.get("schema_version"),
            filename=row.get("filename"),
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.get("/groups", response_model=ProcessGroupsResponse)
def get_process_groups(
    threshold: float = Query(default=0.50, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ProcessGroupsResponse:
    """Return similarity-based groupings of process candidates.

    Downloads all ProcessIR artifacts (up to limit) and computes pairwise
    Jaccard similarity to cluster related processes.  This may be slow for
    large process libraries — use limit to constrain the set.
    """
    with get_connection() as conn:
        rows = list_extraction_results(conn, limit=limit)

    # Download ProcessIR for each result that has a URI
    fingerprints = []
    result_id_map: dict[str, str] = {}  # process_ir.id → extraction_result_id
    for row in rows:
        uri = row.get("process_ir_uri")
        if not uri:
            continue
        data = _download_process_ir(uri)
        if not data:
            continue
        pir = _parse_process_ir(data)
        if not pir:
            continue
        fp = make_fingerprint(pir)
        fingerprints.append(fp)
        result_id_map[pir.id] = str(row["extraction_result_id"])

    clusters = cluster_processes(fingerprints, similarity_threshold=threshold)

    groups = [
        ProcessGroupResponse(
            cluster_id=c.cluster_id,
            process_ids=c.process_ids,
            cohesion=c.cohesion,
            recommend_merge=c.recommend_merge,
            merge_note=c.merge_note,
        )
        for c in clusters
    ]
    singleton_count = sum(1 for g in groups if len(g.process_ids) == 1)

    return ProcessGroupsResponse(groups=groups, singleton_count=singleton_count)


@router.get("/{extraction_result_id}", response_model=ProcessDetailResponse)
def get_process(extraction_result_id: UUID) -> ProcessDetailResponse:
    """Return the structured ProcessIR for a single process candidate.

    Returns structured process facts only — no raw customer content.
    """
    with get_connection() as conn:
        row = get_extraction_result_by_id(conn, extraction_result_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Process {extraction_result_id} not found",
        )

    process_ir_uri = row.get("process_ir_uri")
    if not process_ir_uri:
        return ProcessDetailResponse(
            extraction_result_id=extraction_result_id,
            run_id=row["run_id"],
            schema_version=row.get("schema_version"),
        )

    data = _download_process_ir(process_ir_uri)
    confidence_summary = _build_confidence_summary(data) if data else None

    return ProcessDetailResponse(
        extraction_result_id=extraction_result_id,
        run_id=row["run_id"],
        schema_version=row.get("schema_version"),
        process_ir=data,
        confidence_summary=confidence_summary,
    )


@router.get("/{extraction_result_id}/timeline", response_model=TimelineResponse)
def get_process_timeline(extraction_result_id: UUID) -> TimelineResponse:
    """Return the change timeline for a process candidate.

    Downloads the ProcessIR and extracts change events as a structured timeline.
    No raw customer content is returned.
    """
    with get_connection() as conn:
        row = get_extraction_result_by_id(conn, extraction_result_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Process {extraction_result_id} not found",
        )

    process_ir_uri = row.get("process_ir_uri")
    if not process_ir_uri:
        return TimelineResponse(
            extraction_result_id=extraction_result_id,
            events=[],
            summary={},
        )

    data = _download_process_ir(process_ir_uri)
    if not data:
        return TimelineResponse(
            extraction_result_id=extraction_result_id,
            events=[],
            summary={"error": "ProcessIR unavailable"},
        )

    pir = _parse_process_ir(data)
    if not pir:
        return TimelineResponse(
            extraction_result_id=extraction_result_id,
            events=[],
            summary={"error": "ProcessIR parse error"},
        )

    events = build_timeline(pir)
    # Serialise events — omit raw evidence content, keep structured facts only
    events_payload = [
        {
            "event_id": e.event_id,
            "description": e.description,
            "category": e.category.value,
            "process_id": e.process_id,
            "from_value": e.from_value,
            "to_value": e.to_value,
            "evidence_count": len(e.evidence_refs),
        }
        for e in events
    ]

    # Build a single-version chain for the summary
    from packages.core.process_ir.lineage import LineageChain, ProcessVersion

    version = ProcessVersion(
        process_id=pir.id,
        changes=events,
        version_number=1,
        step_count=len(pir.workflow_steps),
        role_count=len(pir.roles),
        system_count=len(pir.system_touchpoints),
        control_count=len(pir.controls),
    )
    chain = LineageChain(
        chain_id=f"chain_{pir.id}",
        versions=[version],
        timeline=events,
        summary=f"1 version tracked. {len(events)} change event(s) recorded.",
    )
    summary = build_timeline_summary(chain)

    return TimelineResponse(
        extraction_result_id=extraction_result_id,
        process_id=pir.id,
        events=events_payload,
        summary=summary,
    )


@router.get("/{extraction_result_id}/graph", response_model=GraphResponse)
def get_process_graph(extraction_result_id: UUID) -> GraphResponse:
    """Return a React Flow-compatible workflow graph for a process candidate.

    No raw customer content is returned — only structured process facts.
    """
    with get_connection() as conn:
        row = get_extraction_result_by_id(conn, extraction_result_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Process {extraction_result_id} not found",
        )

    process_ir_uri = row.get("process_ir_uri")
    if not process_ir_uri:
        raise HTTPException(
            status_code=404,
            detail=f"No ProcessIR artifact found for process {extraction_result_id}",
        )

    data = _download_process_ir(process_ir_uri)
    if not data:
        raise HTTPException(
            status_code=503,
            detail="ProcessIR artifact unavailable",
        )

    pir = _parse_process_ir(data)
    if not pir:
        raise HTTPException(
            status_code=422,
            detail="ProcessIR artifact could not be parsed",
        )

    graph = project_graph(pir)
    return GraphResponse(
        extraction_result_id=extraction_result_id,
        graph=graph.to_react_flow(),
    )
