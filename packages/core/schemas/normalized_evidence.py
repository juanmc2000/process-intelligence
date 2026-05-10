from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


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
