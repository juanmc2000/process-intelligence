from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SourceSchema(BaseModel):
    id: UUID
    run_id: UUID
    filename: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    input_hash: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
