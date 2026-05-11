"""Pydantic schemas for human review and taxonomy feedback.

Review states for entities and relations:
  accepted           — reviewer confirms the extracted item is correct
  rejected           — reviewer marks the item as incorrect or irrelevant
  edited             — reviewer has modified label or canonical_label
  merged             — reviewer merged this item into another entity
  split              — reviewer split this item into multiple entities
  confidence_override — reviewer has manually set a confidence score

No raw customer content is stored in these schemas.
"""

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Valid review states shared by entity and relation reviews
ReviewState = Literal[
    "accepted",
    "rejected",
    "edited",
    "merged",
    "split",
    "confidence_override",
]

# Valid feedback types for taxonomy feedback
FeedbackType = Literal[
    "new_label",
    "merge_suggestion",
    "split_suggestion",
    "other",
]


class ReviewSessionCreate(BaseModel):
    run_id: UUID
    reviewer_id: Optional[str] = None


class ReviewSessionSchema(BaseModel):
    id: UUID
    run_id: UUID
    reviewer_id: Optional[str] = None
    # status: open | completed | abandoned
    status: str
    created_at: object
    updated_at: object


class EntityReviewCreate(BaseModel):
    review_session_id: UUID
    run_id: UUID
    entity_type: str
    entity_id: str
    review_state: ReviewState
    original_label: Optional[str] = None
    edited_label: Optional[str] = None
    original_canonical_label: Optional[str] = None
    edited_canonical_label: Optional[str] = None
    # confidence_override is only meaningful when review_state = 'confidence_override'
    confidence_override: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reviewer_note: Optional[str] = None


class EntityReviewSchema(EntityReviewCreate):
    id: UUID
    created_at: object
    updated_at: object


class RelationReviewCreate(BaseModel):
    review_session_id: UUID
    run_id: UUID
    relation_type: str
    source_entity_id: str
    target_entity_id: str
    review_state: ReviewState
    original_label: Optional[str] = None
    edited_label: Optional[str] = None
    reviewer_note: Optional[str] = None


class RelationReviewSchema(RelationReviewCreate):
    id: UUID
    created_at: object
    updated_at: object


class TaxonomyFeedbackCreate(BaseModel):
    run_id: UUID
    entity_type: str
    entity_id: str
    feedback_type: FeedbackType
    review_session_id: Optional[UUID] = None
    proposed_label: Optional[str] = None
    notes: Optional[str] = None


class TaxonomyFeedbackSchema(TaxonomyFeedbackCreate):
    id: UUID
    created_at: object
