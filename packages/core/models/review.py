from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class ReviewSession:
    id: UUID
    run_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    reviewer_id: Optional[str] = None


@dataclass
class EntityReview:
    id: UUID
    review_session_id: UUID
    run_id: UUID
    entity_type: str
    entity_id: str
    review_state: str
    created_at: datetime
    updated_at: datetime
    original_label: Optional[str] = None
    edited_label: Optional[str] = None
    original_canonical_label: Optional[str] = None
    edited_canonical_label: Optional[str] = None
    confidence_override: Optional[float] = None
    reviewer_note: Optional[str] = None


@dataclass
class RelationReview:
    id: UUID
    review_session_id: UUID
    run_id: UUID
    relation_type: str
    source_entity_id: str
    target_entity_id: str
    review_state: str
    created_at: datetime
    updated_at: datetime
    original_label: Optional[str] = None
    edited_label: Optional[str] = None
    reviewer_note: Optional[str] = None


@dataclass
class TaxonomyFeedback:
    id: UUID
    run_id: UUID
    entity_type: str
    entity_id: str
    feedback_type: str
    created_at: datetime
    review_session_id: Optional[UUID] = None
    proposed_label: Optional[str] = None
    notes: Optional[str] = None
