"""Temporal activity implementations for the ingestion pipeline."""

from dataclasses import dataclass

from temporalio import activity

from packages.core.database.repository import (
    create_workflow_event,
    update_run_status,
    update_source_status,
)
from packages.core.database.session import get_connection


@dataclass
class ParseInput:
    run_id: str
    source_id: str
    artifact_uri: str


@activity.defn(name="update_run_to_processing")
async def update_run_to_processing(run_id: str) -> None:
    """Set run status to processing and record a workflow event."""
    from uuid import UUID

    with get_connection() as conn:
        update_run_status(conn, UUID(run_id), "processing")
        create_workflow_event(conn, UUID(run_id), "processing_started")

    activity.logger.info("Run %s set to processing", run_id)


@activity.defn(name="parse_artifact")
async def parse_artifact(inp: ParseInput) -> str:
    """Placeholder parser activity — reads raw artifact metadata and writes dummy parsed JSON.

    Returns the object URI of the parsed artifact.
    This stub is intentionally minimal; real parsing is out of scope for Sprint 1.
    """
    import json
    from uuid import UUID

    from packages.core.database.repository import create_artifact
    from packages.core.storage.client import make_storage_client
    from packages.core.storage.operations import (
        default_bucket,
        make_object_key,
        object_uri,
        upload_bytes,
    )

    parsed_payload = json.dumps(
        {
            "run_id": inp.run_id,
            "source_id": inp.source_id,
            "raw_artifact_uri": inp.artifact_uri,
            "parsed_text": "(stub — no real parsing in Sprint 1)",
        }
    ).encode()

    storage = make_storage_client()
    bucket = default_bucket()
    parsed_key = make_object_key(inp.run_id, inp.source_id, "parsed.json", "parsed")
    upload_bytes(storage, bucket, parsed_key, parsed_payload, "application/json")
    uri = object_uri(bucket, parsed_key)

    with get_connection() as conn:
        create_artifact(
            conn,
            run_id=UUID(inp.run_id),
            artifact_type="parsed",
            object_uri=uri,
            source_id=UUID(inp.source_id),
            content_type="application/json",
            size_bytes=len(parsed_payload),
            schema_version="stub-v1",
            deletion_eligible=True,
        )
        update_source_status(conn, UUID(inp.source_id), "parsed")
        create_workflow_event(
            conn,
            UUID(inp.run_id),
            "parse_completed",
            {"parsed_artifact_uri": uri},
        )

    activity.logger.info("Parse stub complete for run %s", inp.run_id)
    return uri
