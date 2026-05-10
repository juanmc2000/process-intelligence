from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class ImageCandidateMetadata(BaseModel):
    """Metadata for a possible process-diagram image detected in a document.

    No image content is stored — only positional and rule-based signals.
    """

    # Where in the document the candidate was found
    page: Optional[int] = None
    location_hint: Optional[str] = None
    # Free-text reasons why this image was flagged (e.g. "filename_signal", "context_keyword")
    reasons: List[str] = []
    # 0.0–1.0 heuristic confidence (deterministic, not ML-derived)
    confidence: float = 0.0


class NormalizedEvidenceMetadata(BaseModel):
    """Structured document/email metadata carried inside the normalized evidence artifact.

    Stored in MinIO as part of the JSON artifact — not in Postgres.
    No raw customer content (body text, file bytes) is included.
    """

    # Common document metadata
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_extension: Optional[str] = None
    page_count: Optional[int] = None
    text_char_count: Optional[int] = None

    # Email-specific metadata
    subject: Optional[str] = None
    sender: Optional[str] = None
    recipients: Optional[List[str]] = None
    cc: Optional[List[str]] = None
    message_id: Optional[str] = None
    # Thread/references headers from the email
    thread_references: Optional[List[str]] = None
    source_date: Optional[datetime] = None
    # Attachment filenames/sizes — no attachment content
    attachment_metadata: Optional[List[Dict[str, Any]]] = None

    # Image candidates detected in documents (metadata only, no OCR)
    image_candidates: Optional[List[ImageCandidateMetadata]] = None


class NormalizedEvidenceSchema(BaseModel):
    """Schema for a normalized evidence record.

    Represents the structured metadata produced by the parser worker.
    The actual artifact content lives in MinIO at artifact_uri — only
    the URI and provenance metadata are stored in Postgres.
    """

    id: UUID
    run_id: UUID
    artifact_uri: str
    content_hash: Optional[str] = None
    parser_version: str
    schema_version: str
    status: str
    created_at: datetime
    updated_at: datetime
    source_id: Optional[UUID] = None
    artifact_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class ExtractionRunSchema(BaseModel):
    id: UUID
    run_id: UUID
    normalized_evidence_id: Optional[UUID] = None
    schema_version: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExtractionResultSchema(BaseModel):
    id: UUID
    extraction_run_id: UUID
    run_id: UUID
    process_ir_uri: str
    schema_version: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExtractionSummary(BaseModel):
    """Lightweight summary embedded in run status responses.

    Avoids returning raw output; exposes only references and status.
    """

    extraction_run_id: UUID
    status: str
    process_ir_uri: Optional[str] = None
    schema_version: Optional[str] = None
