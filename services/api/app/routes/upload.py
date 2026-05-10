import hashlib
import io
import logging
import os
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


class UploadResponse(BaseModel):
    run_id: UUID
    source_id: UUID
    artifact_id: UUID
    status: str
    object_uri: str


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile) -> UploadResponse:
    """Accept a single file, store it in MinIO, and record run/source/artifact metadata."""
    raw_bytes = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload size of {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    input_hash = hashlib.sha256(raw_bytes).hexdigest()
    filename = file.filename or "upload"
    content_type = file.content_type or "application/octet-stream"
    size_bytes = len(raw_bytes)

    storage = make_storage_client()
    bucket = default_bucket()
    ensure_bucket(storage, bucket)

    with get_connection() as conn:
        run_id = create_run(conn, status="uploaded")
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
        )
        create_workflow_event(
            conn,
            run_id=run_id,
            event_type="uploaded",
            payload={"source_id": str(source_id), "artifact_id": str(artifact_id)},
        )

    # Start the Temporal workflow asynchronously — API remains stateless.
    temporal = await make_temporal_client()
    await temporal.start_workflow(
        IngestionRunWorkflow.run,
        args=[str(run_id), str(source_id), uri],
        id=str(run_id),
        task_queue=TASK_QUEUE,
    )

    logger.info("Upload complete run_id=%s source_id=%s", run_id, source_id)
    return UploadResponse(
        run_id=run_id,
        source_id=source_id,
        artifact_id=artifact_id,
        status="uploaded",
        object_uri=uri,
    )
