"""Human review workflow endpoints.

Routes:
  GET  /runs/{run_id}/review          — list review sessions and all review records
  POST /reviews/entities/{entity_id}  — accept / reject / edit an entity
  POST /reviews/relations/{relation_id} — accept / reject / edit a relation
  POST /reviews/taxonomy              — submit taxonomy feedback

All endpoints operate on structured ProcessIR only — no raw customer content
is exposed or stored.
"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from packages.core.database.repository import (
    create_review_session,
    create_taxonomy_feedback,
    get_entity_reviews_for_run,
    get_relation_reviews_for_run,
    get_run,
    get_taxonomy_feedback_for_run,
    list_review_sessions_for_run,
    upsert_entity_review,
    upsert_relation_review,
)
from packages.core.database.session import get_connection

router = APIRouter(tags=["review"])

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

# Valid review states for entities and relations
_REVIEW_STATES = frozenset(
    {"accepted", "rejected", "edited", "merged", "split", "confidence_override"}
)

# Valid feedback types for taxonomy feedback
_FEEDBACK_TYPES = frozenset(
    {"new_label", "merge_suggestion", "split_suggestion", "other"}
)


class EntityReviewRequest(BaseModel):
    """Body for accepting, rejecting, or editing an extracted ProcessIR entity."""

    run_id: UUID
    review_session_id: Optional[UUID] = None
    reviewer_id: Optional[str] = None
    entity_type: str
    # review_state: accepted | rejected | edited | merged | split | confidence_override
    review_state: str
    original_label: Optional[str] = None
    edited_label: Optional[str] = None
    original_canonical_label: Optional[str] = None
    edited_canonical_label: Optional[str] = None
    confidence_override: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reviewer_note: Optional[str] = None


class RelationReviewRequest(BaseModel):
    """Body for accepting, rejecting, or editing an extracted ProcessIR relation."""

    run_id: UUID
    review_session_id: Optional[UUID] = None
    reviewer_id: Optional[str] = None
    relation_type: str
    source_entity_id: str
    target_entity_id: str
    # review_state: accepted | rejected | edited | merged | split | confidence_override
    review_state: str
    original_label: Optional[str] = None
    edited_label: Optional[str] = None
    reviewer_note: Optional[str] = None


class TaxonomyFeedbackRequest(BaseModel):
    """Body for submitting taxonomy label feedback."""

    run_id: UUID
    review_session_id: Optional[UUID] = None
    entity_type: str
    entity_id: str
    # feedback_type: new_label | merge_suggestion | split_suggestion | other
    feedback_type: str
    proposed_label: Optional[str] = None
    notes: Optional[str] = None


class ReviewRecordResponse(BaseModel):
    id: UUID
    # Flexible dict so this covers both entity and relation reviews
    data: dict[str, Any]


class RunReviewSummaryResponse(BaseModel):
    """All review data associated with a run."""

    run_id: UUID
    sessions: list[dict[str, Any]]
    entity_reviews: list[dict[str, Any]]
    relation_reviews: list[dict[str, Any]]
    taxonomy_feedback: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_run(conn: Any, run_id: UUID) -> None:
    """Raise 404 if the run does not exist."""
    if get_run(conn, run_id) is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


def _get_or_create_session(
    conn: Any,
    run_id: UUID,
    review_session_id: Optional[UUID],
    reviewer_id: Optional[str],
) -> UUID:
    """Return an existing session id or create a new open session."""
    if review_session_id is not None:
        return review_session_id
    return create_review_session(conn, run_id, reviewer_id=reviewer_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/review", response_model=RunReviewSummaryResponse)
def get_run_review(run_id: UUID) -> RunReviewSummaryResponse:
    """Return all review sessions, entity reviews, relation reviews, and taxonomy
    feedback for a run.

    Returns only structured ProcessIR metadata — no raw customer content.
    """
    with get_connection() as conn:
        _ensure_run(conn, run_id)
        sessions = list_review_sessions_for_run(conn, run_id)
        entity_reviews = get_entity_reviews_for_run(conn, run_id)
        relation_reviews = get_relation_reviews_for_run(conn, run_id)
        taxonomy_feedback = get_taxonomy_feedback_for_run(conn, run_id)

    return RunReviewSummaryResponse(
        run_id=run_id,
        sessions=sessions,
        entity_reviews=entity_reviews,
        relation_reviews=relation_reviews,
        taxonomy_feedback=taxonomy_feedback,
    )


@router.post("/reviews/entities/{entity_id}", response_model=ReviewRecordResponse)
def review_entity(entity_id: str, body: EntityReviewRequest) -> ReviewRecordResponse:
    """Accept, reject, or edit an extracted ProcessIR entity.

    The entity_id path parameter matches the id field in the ProcessIR JSON.
    A review session is created automatically if review_session_id is not provided.
    """
    if body.review_state not in _REVIEW_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid review_state '{body.review_state}'. "
            f"Must be one of: {sorted(_REVIEW_STATES)}",
        )

    with get_connection() as conn:
        _ensure_run(conn, body.run_id)
        session_id = _get_or_create_session(
            conn, body.run_id, body.review_session_id, body.reviewer_id
        )
        review_id = upsert_entity_review(
            conn,
            review_session_id=session_id,
            run_id=body.run_id,
            entity_type=body.entity_type,
            entity_id=entity_id,
            review_state=body.review_state,
            original_label=body.original_label,
            edited_label=body.edited_label,
            original_canonical_label=body.original_canonical_label,
            edited_canonical_label=body.edited_canonical_label,
            confidence_override=body.confidence_override,
            reviewer_note=body.reviewer_note,
        )

    return ReviewRecordResponse(
        id=review_id,
        data={
            "review_session_id": str(session_id),
            "entity_id": entity_id,
            "entity_type": body.entity_type,
            "review_state": body.review_state,
        },
    )


@router.post("/reviews/relations/{relation_id}", response_model=ReviewRecordResponse)
def review_relation(
    relation_id: str, body: RelationReviewRequest
) -> ReviewRecordResponse:
    """Accept, reject, or edit an extracted ProcessIR relation.

    relation_id is a caller-supplied identifier (e.g. 'step-1->role-2').
    source_entity_id and target_entity_id in the body identify the edge endpoints.
    """
    if body.review_state not in _REVIEW_STATES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid review_state '{body.review_state}'. "
            f"Must be one of: {sorted(_REVIEW_STATES)}",
        )

    with get_connection() as conn:
        _ensure_run(conn, body.run_id)
        session_id = _get_or_create_session(
            conn, body.run_id, body.review_session_id, body.reviewer_id
        )
        review_id = upsert_relation_review(
            conn,
            review_session_id=session_id,
            run_id=body.run_id,
            relation_type=body.relation_type,
            source_entity_id=body.source_entity_id,
            target_entity_id=body.target_entity_id,
            review_state=body.review_state,
            original_label=body.original_label,
            edited_label=body.edited_label,
            reviewer_note=body.reviewer_note,
        )

    return ReviewRecordResponse(
        id=review_id,
        data={
            "review_session_id": str(session_id),
            "relation_id": relation_id,
            "relation_type": body.relation_type,
            "source_entity_id": body.source_entity_id,
            "target_entity_id": body.target_entity_id,
            "review_state": body.review_state,
        },
    )


@router.post("/reviews/taxonomy", response_model=ReviewRecordResponse)
def submit_taxonomy_feedback(body: TaxonomyFeedbackRequest) -> ReviewRecordResponse:
    """Submit taxonomy label feedback for a ProcessIR entity.

    feedback_type: new_label | merge_suggestion | split_suggestion | other
    Does not store raw customer text — only structured taxonomy suggestions.
    """
    if body.feedback_type not in _FEEDBACK_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid feedback_type '{body.feedback_type}'. "
            f"Must be one of: {sorted(_FEEDBACK_TYPES)}",
        )

    with get_connection() as conn:
        _ensure_run(conn, body.run_id)
        feedback_id = create_taxonomy_feedback(
            conn,
            run_id=body.run_id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            feedback_type=body.feedback_type,
            review_session_id=body.review_session_id,
            proposed_label=body.proposed_label,
            notes=body.notes,
        )

    return ReviewRecordResponse(
        id=feedback_id,
        data={
            "entity_type": body.entity_type,
            "entity_id": body.entity_id,
            "feedback_type": body.feedback_type,
        },
    )
