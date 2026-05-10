from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
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
    # --- Sprint 3: document / email lineage metadata ---
    # Date of the document or email (not ingestion date)
    source_date: Optional[datetime] = None
    author: Optional[str] = None
    # Email subject or document title
    subject: Optional[str] = None
    sender: Optional[str] = None
    # List of recipient addresses — stored as JSONB in Postgres
    recipients: Optional[List[str]] = field(default=None)
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    # Original filename before any normalisation
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_extension: Optional[str] = None
    # Parent references for child files extracted from a ZIP
    parent_source_id: Optional[UUID] = None
    parent_artifact_id: Optional[UUID] = None
