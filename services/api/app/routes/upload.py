import hashlib
import io
import logging
import os
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from packages.core.database.repository import (
    create_artifact,
    create_run,
    create_source,
    create_workflow_event,
)
from packages.core.database.session import get_connection
from packages.core.storage.client import make_storage_client
from packages.core.storage.operations import (
    default_bucket,
    ensure_bucket,
    make_object_key,
    object_uri,
    upload_fileobj,
)
from packages.core.workflows.client import make_temporal_client
from packages.core.workflows.ingestion import IngestionRunWorkflow, TASK_QUEUE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])

_MAX_UPLOAD_BYTES = int(os.environ.get("UPLOAD_MAX_SIZE_MB", "50")) * 1024 * 1024
_MAX_FILES_PER_REQUEST = int(os.environ.get("UPLOAD_MAX_FILES", "20"))


class SourceUploadSummary(BaseModel):
    """Metadata for one uploaded file within a multi-file request."""

    source_id: UUID
    artifact_id: UUID
    filename: str
    object_uri: str


class UploadResponse(BaseModel):
    """Response for POST /runs/upload.

    One run is created per request.  Each uploaded file produces one source
    and one raw artifact.  A Temporal workflow is started for each source.
    """

    run_id: UUID
    status: str
    sources: List[SourceUploadSummary]


@router.post("/upload", response_model=UploadResponse)
async def upload_files(files: List[UploadFile]) -> UploadResponse:
    """Accept one or more files, store each in MinIO, and trigger the ingestion workflow.

    One run is created per request.  For each uploaded file a source record and
    a raw artifact record are created, and a Temporal workflow is started.
    Files are not parsed here — all heavy processing is delegated to workers.
    """
    if not files:
        raise HTTPException(status_code=422, detail="At least one file is required.")
    if len(files) > _MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"Too many files: maximum {_MAX_FILES_PER_REQUEST} per request.",
        )

    storage = make_storage_client()
    bucket = default_bucket()
    ensure_bucket(storage, bucket)

    # Read all file bytes first so we can validate sizes before writing to storage.
    file_payloads = []
    for file in files:
        raw_bytes = await file.read(_MAX_UPLOAD_BYTES + 1)
        if len(raw_bytes) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File '{file.filename}' exceeds maximum upload size of "
                    f"{_MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
                ),
            )
        file_payloads.append(
            {
                "filename": file.filename or "upload",
                "content_type": file.content_type or "application/octet-stream",
                "raw_bytes": raw_bytes,
                "size_bytes": len(raw_bytes),
                "input_hash": hashlib.sha256(raw_bytes).hexdigest(),
            }
        )

    # Create a single run for this batch of uploads.
    with get_connection() as conn:
        run_id = create_run(conn, status="uploaded")

    # Create one source + artifact per file and upload raw bytes to MinIO.
    summaries: List[SourceUploadSummary] = []
    for payload in file_payloads:
        filename = payload["filename"]
        content_type = payload["content_type"]
        raw_bytes = payload["raw_bytes"]
        size_bytes = payload["size_bytes"]
        input_hash = payload["input_hash"]

        with get_connection() as conn:
            source_id = create_source(
                conn,
                run_id=run_id,
                filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
                input_hash=input_hash,
                status="uploaded",
            )

            key = make_object_key(
                run_id=str(run_id),
                source_id=str(source_id),
                filename=filename,
                artifact_type="raw",
            )
            upload_fileobj(
                storage,
                bucket,
                key,
                io.BytesIO(raw_bytes),
                size_bytes,
                content_type,
            )
            uri = object_uri(bucket, key)

            artifact_id = create_artifact(
                conn,
                run_id=run_id,
                artifact_type="raw",
                object_uri=uri,
                source_id=source_id,
                content_type=content_type,
                size_bytes=size_bytes,
                deletion_eligible=True,
                retention_class="temporary",
            )
            create_workflow_event(
                conn,
                run_id=run_id,
                event_type="uploaded",
                payload={"source_id": str(source_id), "artifact_id": str(artifact_id)},
            )

        summaries.append(
            SourceUploadSummary(
                source_id=source_id,
                artifact_id=artifact_id,
                filename=filename,
                object_uri=uri,
            )
        )

    # Start one Temporal workflow per source — each processes one artifact.
    # Workflow IDs are {run_id}-{source_id} to be unique and traceable.
    temporal = await make_temporal_client()
    for summary in summaries:
        await temporal.start_workflow(
            IngestionRunWorkflow.run,
            args=[str(run_id), str(summary.source_id), summary.object_uri],
            id=f"{run_id}-{summary.source_id}",
            task_queue=TASK_QUEUE,
        )

    logger.info("Upload complete run_id=%s files=%d", run_id, len(summaries))
    return UploadResponse(run_id=run_id, status="uploaded", sources=summaries)
