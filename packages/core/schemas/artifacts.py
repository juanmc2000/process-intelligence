from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ArtifactSchema(BaseModel):
    id: UUID
    run_id: UUID
    source_id: Optional[UUID] = None
    artifact_type: str
    object_uri: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    schema_version: Optional[str] = None
    deletion_eligible: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
