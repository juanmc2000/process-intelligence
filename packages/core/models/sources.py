from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Source:
    id: UUID
    run_id: UUID
    filename: str
    status: str
    created_at: datetime
    updated_at: datetime
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    input_hash: Optional[str] = None
