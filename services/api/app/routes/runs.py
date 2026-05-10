from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.core.database.repository import get_extraction_summary, get_run
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
