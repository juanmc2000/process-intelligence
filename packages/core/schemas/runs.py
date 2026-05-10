from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class RunSchema(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}
