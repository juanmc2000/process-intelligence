from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class NormalizedEvidenceRecord:
    id: UUID
    run_id: UUID
    artifact_uri: str
    parser_version: str
    schema_version: str
    status: str
    created_at: datetime
    updated_at: datetime
    source_id: Optional[UUID] = None
    artifact_id: Optional[UUID] = None
    content_hash: Optional[str] = None


@dataclass
class ExtractionRun:
    id: UUID
    run_id: UUID
    schema_version: str
    status: str
    created_at: datetime
    updated_at: datetime
    normalized_evidence_id: Optional[UUID] = None
    error_message: Optional[str] = None


@dataclass
class ExtractionResult:
    id: UUID
    extraction_run_id: UUID
    run_id: UUID
    process_ir_uri: str
    schema_version: str
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ModelInvocation:
    id: UUID
    extraction_run_id: UUID
    model_name: str
    prompt_version: str
    status: str
    created_at: datetime
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None
