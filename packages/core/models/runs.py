from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Run:
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
