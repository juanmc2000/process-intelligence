from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class WorkflowEventSchema(BaseModel):
    id: UUID
    run_id: UUID
    event_type: str
    payload: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}
