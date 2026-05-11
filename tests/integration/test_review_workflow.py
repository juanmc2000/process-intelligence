"""Integration tests for the human review workflow.

Tests the review repository helpers and Pydantic schema validation using
synthetic fixtures. No external infrastructure required (no DB, no MinIO,
no Temporal, no FastAPI runtime).

Repository tests use a mock psycopg2 connection pattern consistent with
the rest of the integration test suite.

psycopg2 is not installed in the test venv (it runs inside Docker only),
so we stub it in sys.modules before importing any database code.
"""

import sys
import types
import uuid
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub psycopg2 so that packages.core.database.repository can be imported
# in the test venv (which lacks psycopg2-binary).
# ---------------------------------------------------------------------------

if "psycopg2" not in sys.modules:
    _psycopg2 = types.ModuleType("psycopg2")
    _psycopg2.__path__ = []  # mark as package so submodules can be found
    _psycopg2_ext = types.ModuleType("psycopg2.extensions")
    _psycopg2_ext.connection = object  # type: ignore[attr-defined]
    _psycopg2_extras = types.ModuleType("psycopg2.extras")
    _psycopg2_extras.RealDictCursor = MagicMock  # type: ignore[attr-defined]
    _psycopg2.extensions = _psycopg2_ext  # type: ignore[attr-defined]
    _psycopg2.extras = _psycopg2_extras  # type: ignore[attr-defined]
    sys.modules["psycopg2"] = _psycopg2
    sys.modules["psycopg2.extensions"] = _psycopg2_ext
    sys.modules["psycopg2.extras"] = _psycopg2_extras

from packages.core.schemas.review import (
    EntityReviewCreate,
    RelationReviewCreate,
    ReviewSessionCreate,
    TaxonomyFeedbackCreate,
)

# ---------------------------------------------------------------------------
# Synthetic IDs (no real customer content)
# ---------------------------------------------------------------------------

_RUN_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_SESSION_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
_ENTITY_REVIEW_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000003")
_RELATION_REVIEW_ID = uuid.UUID("dddddddd-0000-0000-0000-000000000004")
_TAXONOMY_FEEDBACK_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000005")


# ---------------------------------------------------------------------------
# Mock connection helpers
# ---------------------------------------------------------------------------


def _make_cursor(return_id: uuid.UUID) -> MagicMock:
    """Return a cursor mock whose fetchone() yields {"id": return_id}."""
    cursor = MagicMock()
    cursor.__enter__ = lambda s: cursor
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.return_value = {"id": return_id}
    cursor.fetchall.return_value = []
    return cursor


def _make_conn(return_id: uuid.UUID) -> MagicMock:
    """Return a connection mock using the single-return_id cursor."""
    conn = MagicMock()
    cursor = _make_cursor(return_id)
    conn.cursor.return_value = cursor
    return conn


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestReviewSchemaValidation:
    """Pydantic schemas enforce valid review states and feedback types."""

    def test_valid_entity_review_accepted(self):
        schema = EntityReviewCreate(
            review_session_id=_SESSION_ID,
            run_id=_RUN_ID,
            entity_type="workflow_step",
            entity_id="step-1",
            review_state="accepted",
        )
        assert schema.review_state == "accepted"

    def test_valid_entity_review_all_states(self):
        for state in (
            "accepted",
            "rejected",
            "edited",
            "merged",
            "split",
            "confidence_override",
        ):
            s = EntityReviewCreate(
                review_session_id=_SESSION_ID,
                run_id=_RUN_ID,
                entity_type="role",
                entity_id="role-1",
                review_state=state,
            )
            assert s.review_state == state

    def test_invalid_entity_review_state_rejected(self):
        """Pydantic should reject an unknown review_state."""
        with pytest.raises(Exception):
            EntityReviewCreate(
                review_session_id=_SESSION_ID,
                run_id=_RUN_ID,
                entity_type="role",
                entity_id="role-1",
                review_state="not_valid",
            )

    def test_confidence_override_bounds(self):
        """confidence_override must be between 0.0 and 1.0."""
        with pytest.raises(Exception):
            EntityReviewCreate(
                review_session_id=_SESSION_ID,
                run_id=_RUN_ID,
                entity_type="workflow_step",
                entity_id="step-1",
                review_state="confidence_override",
                confidence_override=1.5,  # out of bounds
            )

    def test_valid_relation_review(self):
        schema = RelationReviewCreate(
            review_session_id=_SESSION_ID,
            run_id=_RUN_ID,
            relation_type="performed_by",
            source_entity_id="step-1",
            target_entity_id="role-1",
            review_state="accepted",
        )
        assert schema.relation_type == "performed_by"

    def test_invalid_relation_review_state(self):
        with pytest.raises(Exception):
            RelationReviewCreate(
                review_session_id=_SESSION_ID,
                run_id=_RUN_ID,
                relation_type="performed_by",
                source_entity_id="step-1",
                target_entity_id="role-1",
                review_state="unknown_state",
            )

    def test_valid_taxonomy_feedback_types(self):
        for ft in ("new_label", "merge_suggestion", "split_suggestion", "other"):
            s = TaxonomyFeedbackCreate(
                run_id=_RUN_ID,
                entity_type="workflow_step",
                entity_id="step-1",
                feedback_type=ft,
            )
            assert s.feedback_type == ft

    def test_invalid_taxonomy_feedback_type(self):
        with pytest.raises(Exception):
            TaxonomyFeedbackCreate(
                run_id=_RUN_ID,
                entity_type="workflow_step",
                entity_id="step-1",
                feedback_type="bad_type",
            )

    def test_review_session_create(self):
        schema = ReviewSessionCreate(run_id=_RUN_ID, reviewer_id="reviewer@example.com")
        assert schema.reviewer_id == "reviewer@example.com"

    def test_no_reviewer_id_optional(self):
        schema = ReviewSessionCreate(run_id=_RUN_ID)
        assert schema.reviewer_id is None


# ---------------------------------------------------------------------------
# Repository helper tests
# ---------------------------------------------------------------------------


class TestReviewSessionRepository:
    def test_create_review_session_returns_id(self):
        from packages.core.database.repository import create_review_session

        conn = _make_conn(_SESSION_ID)
        result = create_review_session(conn, _RUN_ID, reviewer_id="reviewer@test.com")
        assert result == _SESSION_ID
        conn.cursor.assert_called_once()

    def test_create_review_session_default_status_open(self):
        from packages.core.database.repository import create_review_session

        conn = _make_conn(_SESSION_ID)
        create_review_session(conn, _RUN_ID)
        cursor = conn.cursor.return_value
        # Verify SQL was called with 'open' as status
        call_args = cursor.execute.call_args
        assert "open" in call_args[0][1]

    def test_get_review_session_returns_dict(self):
        from packages.core.database.repository import get_review_session

        conn = MagicMock()
        cursor = MagicMock()
        cursor.__enter__ = lambda s: cursor
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchone.return_value = {
            "id": _SESSION_ID,
            "run_id": _RUN_ID,
            "status": "open",
        }
        conn.cursor.return_value = cursor

        result = get_review_session(conn, _SESSION_ID)
        assert result is not None
        assert result["id"] == _SESSION_ID

    def test_get_review_session_not_found(self):
        from packages.core.database.repository import get_review_session

        conn = MagicMock()
        cursor = MagicMock()
        cursor.__enter__ = lambda s: cursor
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor

        result = get_review_session(conn, _SESSION_ID)
        assert result is None

    def test_list_review_sessions_for_run(self):
        from packages.core.database.repository import list_review_sessions_for_run

        conn = MagicMock()
        cursor = MagicMock()
        cursor.__enter__ = lambda s: cursor
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchall.return_value = [
            {"id": _SESSION_ID, "run_id": _RUN_ID, "status": "open"}
        ]
        conn.cursor.return_value = cursor

        result = list_review_sessions_for_run(conn, _RUN_ID)
        assert len(result) == 1
        assert result[0]["status"] == "open"


class TestEntityReviewRepository:
    def test_upsert_entity_review_returns_id(self):
        from packages.core.database.repository import upsert_entity_review

        conn = _make_conn(_ENTITY_REVIEW_ID)
        result = upsert_entity_review(
            conn,
            review_session_id=_SESSION_ID,
            run_id=_RUN_ID,
            entity_type="workflow_step",
            entity_id="step-1",
            review_state="accepted",
        )
        assert result == _ENTITY_REVIEW_ID

    def test_upsert_entity_review_with_edit(self):
        from packages.core.database.repository import upsert_entity_review

        conn = _make_conn(_ENTITY_REVIEW_ID)
        result = upsert_entity_review(
            conn,
            review_session_id=_SESSION_ID,
            run_id=_RUN_ID,
            entity_type="workflow_step",
            entity_id="step-1",
            review_state="edited",
            original_label="Original Step",
            edited_label="Revised Step",
        )
        assert result == _ENTITY_REVIEW_ID
        cursor = conn.cursor.return_value
        # Ensure the edited label was passed to the SQL call
        call_args = cursor.execute.call_args[0][1]
        assert "Revised Step" in call_args

    def test_get_entity_reviews_for_run_returns_list(self):
        from packages.core.database.repository import get_entity_reviews_for_run

        conn = MagicMock()
        cursor = MagicMock()
        cursor.__enter__ = lambda s: cursor
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchall.return_value = [
            {
                "id": _ENTITY_REVIEW_ID,
                "entity_id": "step-1",
                "review_state": "accepted",
            }
        ]
        conn.cursor.return_value = cursor

        result = get_entity_reviews_for_run(conn, _RUN_ID)
        assert len(result) == 1
        assert result[0]["review_state"] == "accepted"


class TestRelationReviewRepository:
    def test_upsert_relation_review_returns_id(self):
        from packages.core.database.repository import upsert_relation_review

        conn = _make_conn(_RELATION_REVIEW_ID)
        result = upsert_relation_review(
            conn,
            review_session_id=_SESSION_ID,
            run_id=_RUN_ID,
            relation_type="performed_by",
            source_entity_id="step-1",
            target_entity_id="role-1",
            review_state="accepted",
        )
        assert result == _RELATION_REVIEW_ID

    def test_get_relation_reviews_for_run_returns_list(self):
        from packages.core.database.repository import get_relation_reviews_for_run

        conn = MagicMock()
        cursor = MagicMock()
        cursor.__enter__ = lambda s: cursor
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchall.return_value = [
            {"id": _RELATION_REVIEW_ID, "review_state": "rejected"}
        ]
        conn.cursor.return_value = cursor

        result = get_relation_reviews_for_run(conn, _RUN_ID)
        assert len(result) == 1
        assert result[0]["review_state"] == "rejected"


class TestTaxonomyFeedbackRepository:
    def test_create_taxonomy_feedback_returns_id(self):
        from packages.core.database.repository import create_taxonomy_feedback

        conn = _make_conn(_TAXONOMY_FEEDBACK_ID)
        result = create_taxonomy_feedback(
            conn,
            run_id=_RUN_ID,
            entity_type="workflow_step",
            entity_id="step-1",
            feedback_type="new_label",
            proposed_label="Better Name",
        )
        assert result == _TAXONOMY_FEEDBACK_ID

    def test_get_taxonomy_feedback_for_run_returns_list(self):
        from packages.core.database.repository import get_taxonomy_feedback_for_run

        conn = MagicMock()
        cursor = MagicMock()
        cursor.__enter__ = lambda s: cursor
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchall.return_value = [
            {"id": _TAXONOMY_FEEDBACK_ID, "feedback_type": "new_label"}
        ]
        conn.cursor.return_value = cursor

        result = get_taxonomy_feedback_for_run(conn, _RUN_ID)
        assert len(result) == 1
        assert result[0]["feedback_type"] == "new_label"

    def test_taxonomy_feedback_without_session(self):
        """Taxonomy feedback may be submitted without a review session."""
        from packages.core.database.repository import create_taxonomy_feedback

        conn = _make_conn(_TAXONOMY_FEEDBACK_ID)
        result = create_taxonomy_feedback(
            conn,
            run_id=_RUN_ID,
            entity_type="role",
            entity_id="role-1",
            feedback_type="merge_suggestion",
            review_session_id=None,
        )
        assert result == _TAXONOMY_FEEDBACK_ID
        cursor = conn.cursor.return_value
        call_args = cursor.execute.call_args[0][1]
        # review_session_id should be None in the SQL params
        assert call_args[0] is None
