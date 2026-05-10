from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Artifact:
    id: UUID
    run_id: UUID
    artifact_type: str  # 'raw' | 'normalized_evidence' | 'process_ir'
    object_uri: str
    created_at: datetime
    updated_at: datetime
    source_id: Optional[UUID] = None
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    schema_version: Optional[str] = None
    retention_class: str = "temporary"  # 'temporary' | 'durable'
    deletion_eligible: bool = False
    deleted_at: Optional[datetime] = None
    purge_after: Optional[datetime] = None
