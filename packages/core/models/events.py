from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


@dataclass
class WorkflowEvent:
    id: UUID
    run_id: UUID
    event_type: str
    created_at: datetime
    payload: Optional[dict[str, Any]] = None
