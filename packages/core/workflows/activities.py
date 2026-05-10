"""Temporal activity implementations for the ingestion pipeline."""

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from temporalio import activity

from packages.core.database.repository import (
    create_workflow_event,
    update_run_status,
    update_source_status,
)
from packages.core.database.session import get_connection

_PARSER_VERSION = "1.0.0"
_NORMALIZED_EVIDENCE_SCHEMA_VERSION = "normalized-evidence-v1"
_PROCESS_IR_SCHEMA_VERSION = "process-ir-v1"


@dataclass
class ParseInput:
    run_id: str
    source_id: str
    artifact_uri: str
    # Optional hints passed from the upload route (Sprint 3)
    content_type: str = ""
    original_filename: str = ""


@dataclass
class ExtractInput:
    run_id: str
    normalized_evidence_uri: str
    normalized_evidence_id: str


@activity.defn(name="update_run_to_processing")
async def update_run_to_processing(run_id: str) -> None:
    """Set run status to processing and record a workflow event."""
    with get_connection() as conn:
        update_run_status(conn, UUID(run_id), "processing")
        create_workflow_event(conn, UUID(run_id), "processing_started")

    activity.logger.info("Run %s set to processing", run_id)


@activity.defn(name="parse_artifact")
async def parse_artifact(inp: ParseInput) -> dict:
    """Parser activity — writes a normalized evidence artifact to MinIO.

    Dispatches to format-specific parsers (PDF, EML, ZIP) based on
    content_type and filename.  Falls back to a generic metadata stub for
    any unsupported format.

    Normalized evidence contains structural metadata and source references only.
    No raw customer content is included in the output.

    Returns a dict with normalized_evidence_uri and normalized_evidence_id.
    """
    from packages.core.database.repository import (
        create_artifact,
        create_normalized_evidence,
    )
    from packages.core.storage.client import make_storage_client
    from packages.core.storage.operations import (
        default_bucket,
        download_bytes,
        make_object_key,
        object_uri,
        parse_object_uri,
        upload_bytes,
    )

    storage = make_storage_client()
    bucket = default_bucket()

    # Download the raw artifact so format-specific parsers can read it.
    raw_bucket, raw_key = parse_object_uri(inp.artifact_uri)
    raw_bytes = download_bytes(storage, raw_bucket, raw_key)

    filename = inp.original_filename or inp.artifact_uri.rsplit("/", 1)[-1]
    content_type = inp.content_type or ""

    # Dispatch to format-specific parsers; collect format metadata.
    format_metadata: dict = _dispatch_parse(raw_bytes, filename, content_type)

    content_hash = format_metadata.get(
        "content_hash",
        "sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
    )

    normalized_payload = json.dumps(
        {
            "run_id": inp.run_id,
            "source_id": inp.source_id,
            "parser_version": _PARSER_VERSION,
            "schema_version": _NORMALIZED_EVIDENCE_SCHEMA_VERSION,
            "raw_artifact_uri": inp.artifact_uri,
            "content_hash": content_hash,
            **format_metadata,
        }
    ).encode()

    key = make_object_key(
        inp.run_id, inp.source_id, "normalized_evidence.json", "normalized"
    )
    upload_bytes(storage, bucket, key, normalized_payload, "application/json")
    uri = object_uri(bucket, key)

    with get_connection() as conn:
        artifact_id = create_artifact(
            conn,
            run_id=UUID(inp.run_id),
            artifact_type="normalized_evidence",
            object_uri=uri,
            source_id=UUID(inp.source_id),
            content_type="application/json",
            size_bytes=len(normalized_payload),
            schema_version=_NORMALIZED_EVIDENCE_SCHEMA_VERSION,
            # Normalized evidence is temporary — eligible for deletion after extraction
            deletion_eligible=True,
            retention_class="temporary",
        )
        ne_id = create_normalized_evidence(
            conn,
            run_id=UUID(inp.run_id),
            artifact_uri=uri,
            parser_version=_PARSER_VERSION,
            schema_version=_NORMALIZED_EVIDENCE_SCHEMA_VERSION,
            source_id=UUID(inp.source_id),
            artifact_id=artifact_id,
            content_hash=content_hash,
        )
        update_source_status(conn, UUID(inp.source_id), "parsed")
        create_workflow_event(
            conn,
            UUID(inp.run_id),
            "parse_completed",
            {
                "normalized_evidence_uri": uri,
                "format": format_metadata.get("format", "unknown"),
            },
        )

    activity.logger.info(
        "Parser complete for run %s (format=%s)",
        inp.run_id,
        format_metadata.get("format", "unknown"),
    )
    return {"normalized_evidence_uri": uri, "normalized_evidence_id": str(ne_id)}


def _dispatch_parse(raw_bytes: bytes, filename: str, content_type: str) -> dict:
    """Route raw artifact bytes to the appropriate format parser.

    Returns a metadata dict merged into the normalized evidence JSON.
    Never logs or returns raw content.
    """
    from services.workers.parser.eml import is_eml, parse_eml
    from services.workers.parser.pdf import is_pdf, parse_pdf

    if is_pdf(content_type, filename):
        try:
            return parse_pdf(raw_bytes, filename)
        except Exception as exc:
            # Non-fatal: fall back to generic metadata if PDF is unreadable.
            activity.logger.warning("PDF parse failed for '%s': %s", filename, exc)
            return _generic_metadata(raw_bytes, filename, content_type)

    if is_eml(content_type, filename):
        try:
            return parse_eml(raw_bytes, filename)
        except Exception as exc:
            # Non-fatal: fall back to generic metadata if EML is malformed.
            activity.logger.warning("EML parse failed for '%s': %s", filename, exc)
            return _generic_metadata(raw_bytes, filename, content_type)

    return _generic_metadata(raw_bytes, filename, content_type)


def _generic_metadata(raw_bytes: bytes, filename: str, content_type: str) -> dict:
    """Produce minimal structural metadata for unsupported/plain-text formats."""
    import os

    content_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    ext = os.path.splitext(filename)[1].lower()
    return {
        "format": "generic",
        "original_filename": filename,
        "mime_type": content_type or "application/octet-stream",
        "file_extension": ext,
        "text_char_count": len(raw_bytes),
        "content_hash": content_hash,
    }


@activity.defn(name="extract_process_ir")
async def extract_process_ir(inp: ExtractInput) -> str:
    """Deterministic ProcessIR extraction stub.

    Reads normalized evidence artifact metadata and produces a ProcessIR artifact
    without calling any external LLM. This stub always produces a valid, empty ProcessIR
    that is schema-conformant and traceable via run_id.

    Returns the object URI of the ProcessIR artifact.
    """
    from packages.core.database.repository import (
        create_artifact,
        create_extraction_result,
        create_extraction_run,
        update_extraction_run_status,
    )
    from packages.core.storage.client import make_storage_client
    from packages.core.storage.operations import (
        default_bucket,
        make_object_key,
        object_uri,
        upload_bytes,
    )

    with get_connection() as conn:
        extraction_run_id = create_extraction_run(
            conn,
            run_id=UUID(inp.run_id),
            schema_version=_PROCESS_IR_SCHEMA_VERSION,
            normalized_evidence_id=UUID(inp.normalized_evidence_id),
            status="running",
        )
        create_workflow_event(
            conn,
            UUID(inp.run_id),
            "extraction_started",
            {"extraction_run_id": str(extraction_run_id)},
        )

    # Deterministic stub — no LLM call, produces an empty but valid ProcessIR
    process_ir_payload = json.dumps(
        {
            "id": str(extraction_run_id),
            "run_id": inp.run_id,
            "source_artifact_uri": inp.normalized_evidence_uri,
            "schema_version": _PROCESS_IR_SCHEMA_VERSION,
            "workflow_steps": [],
            "decision_points": [],
            "system_touchpoints": [],
            "roles": [],
            "controls": [],
            "exceptions": [],
            "change_events": [],
        }
    ).encode()

    storage = make_storage_client()
    bucket = default_bucket()
    key = make_object_key(
        inp.run_id, str(extraction_run_id), "process_ir.json", "process_ir"
    )
    upload_bytes(storage, bucket, key, process_ir_payload, "application/json")
    process_ir_uri = object_uri(bucket, key)

    with get_connection() as conn:
        create_artifact(
            conn,
            run_id=UUID(inp.run_id),
            artifact_type="process_ir",
            object_uri=process_ir_uri,
            content_type="application/json",
            size_bytes=len(process_ir_payload),
            schema_version=_PROCESS_IR_SCHEMA_VERSION,
            # ProcessIR is durable — not eligible for deletion
            deletion_eligible=False,
            retention_class="durable",
        )
        create_extraction_result(
            conn,
            extraction_run_id=extraction_run_id,
            run_id=UUID(inp.run_id),
            process_ir_uri=process_ir_uri,
            schema_version=_PROCESS_IR_SCHEMA_VERSION,
        )
        update_extraction_run_status(conn, extraction_run_id, "completed")
        create_workflow_event(
            conn,
            UUID(inp.run_id),
            "extraction_completed",
            {
                "extraction_run_id": str(extraction_run_id),
                "process_ir_uri": process_ir_uri,
            },
        )

    activity.logger.info("Extraction stub complete for run %s", inp.run_id)
    return process_ir_uri
