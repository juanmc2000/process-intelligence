import json
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.core.database.repository import (
    get_extraction_summary,
    get_process_ir_for_run,
    get_run,
)
from packages.core.database.session import get_connection

router = APIRouter(prefix="/runs", tags=["runs"])


class ArtifactResponse(BaseModel):
    id: UUID
    artifact_type: str
    object_uri: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    deletion_eligible: bool
    created_at: Any


class SourceResponse(BaseModel):
    id: UUID
    filename: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    input_hash: Optional[str] = None
    status: str
    created_at: Any


class WorkflowEventResponse(BaseModel):
    id: UUID
    event_type: str
    payload: Optional[dict[str, Any]] = None
    created_at: Any


class ExtractionSummaryResponse(BaseModel):
    """Extraction progress and ProcessIR artifact reference.

    Only metadata is returned — no raw LLM output or customer content.
    """

    extraction_run_id: UUID
    status: str
    process_ir_uri: Optional[str] = None
    schema_version: Optional[str] = None


class ProcessIRResponse(BaseModel):
    """Structured ProcessIR output for a completed run.

    Returns only structured process facts — never raw customer content.
    """

    run_id: UUID
    source_id: Optional[UUID] = None
    extraction_result_id: Optional[UUID] = None
    extraction_status: str
    schema_version: Optional[str] = None
    process_ir: Optional[dict[str, Any]] = None
    confidence_summary: Optional[dict[str, Any]] = None


class RunDetailResponse(BaseModel):
    id: UUID
    status: str
    error_message: Optional[str] = None
    created_at: Any
    updated_at: Any
    sources: list[SourceResponse]
    artifacts: list[ArtifactResponse]
    workflow_events: list[WorkflowEventResponse]
    extraction: Optional[ExtractionSummaryResponse] = None


@router.get("/{run_id}", response_model=RunDetailResponse)
def get_run_status(run_id: UUID) -> RunDetailResponse:
    """Return run metadata, sources, artifacts, workflow events, and extraction summary."""
    with get_connection() as conn:
        run = get_run(conn, run_id)
        extraction = get_extraction_summary(conn, run_id)

    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    extraction_response: Optional[ExtractionSummaryResponse] = None
    if extraction:
        extraction_response = ExtractionSummaryResponse(
            extraction_run_id=extraction["extraction_run_id"],
            status=extraction["status"],
            process_ir_uri=extraction.get("process_ir_uri"),
            schema_version=extraction.get("schema_version"),
        )

    return RunDetailResponse(
        id=run["id"],
        status=run["status"],
        error_message=run.get("error_message"),
        created_at=run["created_at"],
        updated_at=run["updated_at"],
        sources=[SourceResponse(**s) for s in run["sources"]],
        artifacts=[ArtifactResponse(**a) for a in run["artifacts"]],
        workflow_events=[WorkflowEventResponse(**e) for e in run["workflow_events"]],
        extraction=extraction_response,
    )


@router.get("/{run_id}/process-ir", response_model=ProcessIRResponse)
def get_process_ir(run_id: UUID) -> ProcessIRResponse:
    """Return the structured ProcessIR artifact for a completed run.

    Returns only structured process intelligence — no raw customer content.
    If extraction is not yet complete, returns the current extraction status.
    """
    with get_connection() as conn:
        run = get_run(conn, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        ir_meta = get_process_ir_for_run(conn, run_id)

    if ir_meta is None:
        raise HTTPException(
            status_code=404,
            detail=f"No extraction found for run {run_id}",
        )

    extraction_status = ir_meta["extraction_status"]
    process_ir_uri = ir_meta.get("process_ir_uri")

    # If extraction is not complete or has no URI, return status only
    if extraction_status != "completed" or not process_ir_uri:
        return ProcessIRResponse(
            run_id=run_id,
            source_id=ir_meta.get("source_id"),
            extraction_result_id=ir_meta.get("extraction_result_id"),
            extraction_status=extraction_status,
            schema_version=ir_meta.get("schema_version"),
        )

    # Download ProcessIR artifact from MinIO
    process_ir_data = _download_process_ir(process_ir_uri)

    # Build confidence summary from the ProcessIR data
    confidence_summary = _build_confidence_summary(process_ir_data)

    return ProcessIRResponse(
        run_id=run_id,
        source_id=ir_meta.get("source_id"),
        extraction_result_id=ir_meta.get("extraction_result_id"),
        extraction_status=extraction_status,
        schema_version=ir_meta.get("schema_version"),
        process_ir=process_ir_data,
        confidence_summary=confidence_summary,
    )


def _download_process_ir(process_ir_uri: str) -> Optional[dict[str, Any]]:
    """Download and parse ProcessIR JSON from MinIO."""
    from packages.core.storage.client import make_storage_client
    from packages.core.storage.operations import download_bytes, parse_object_uri

    try:
        bucket, key = parse_object_uri(process_ir_uri)
        storage = make_storage_client()
        data = download_bytes(storage, bucket, key)
        return json.loads(data)
    except Exception:
        return None


def _build_confidence_summary(
    process_ir: Optional[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """Build a summary of extraction counts from ProcessIR data."""
    if process_ir is None:
        return None

    return {
        "workflow_step_count": len(process_ir.get("workflow_steps", [])),
        "decision_point_count": len(process_ir.get("decision_points", [])),
        "system_touchpoint_count": len(process_ir.get("system_touchpoints", [])),
        "role_count": len(process_ir.get("roles", [])),
        "control_count": len(process_ir.get("controls", [])),
        "exception_count": len(process_ir.get("exceptions", [])),
        "change_event_count": len(process_ir.get("change_events", [])),
    }
