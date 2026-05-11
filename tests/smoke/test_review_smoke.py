"""Smoke tests for the review workflow API endpoints.

Requires the full docker-compose stack to be running WITH the review endpoints
deployed (API-007 merged to main):
    docker compose up -d

Run with:
    pytest tests/smoke/test_review_smoke.py -v

Tests are skipped automatically if the review endpoints are not yet deployed.
"""

import io
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("SMOKE_API_URL", "http://localhost:8010")
_POLL_INTERVAL = 2  # seconds
_POLL_TIMEOUT = 90  # seconds


def _review_endpoints_available() -> bool:
    """Return True if the /runs/{id}/review endpoint responds as a known route."""
    try:
        # A missing run returns {"detail": "Run ... not found"};
        # a missing route returns {"detail": "Not Found"} — distinguish by detail text.
        resp = requests.get(
            f"{BASE_URL}/runs/00000000-0000-0000-0000-000000000000/review",
            timeout=5,
        )
        if resp.status_code == 404:
            detail = resp.json().get("detail", "")
            # Route not found produces generic "Not Found"; run not found is specific
            return "Not Found" not in detail
        return resp.status_code < 500
    except Exception:
        return False


_SKIP_REVIEW = pytest.mark.skipif(
    not _review_endpoints_available(),
    reason="Review endpoints not deployed on running stack — skipping smoke tests",
)


def _get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", **kwargs)


def _post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", **kwargs)


def _upload_and_wait() -> str:
    """Upload a minimal synthetic artifact and poll until extraction completes.

    Returns the run_id of the completed run.
    """
    content = b"process: order-to-cash\nsteps: receive, validate, ship, invoice"
    resp = _post(
        "/runs/upload",
        files=[("files", ("review_smoke.txt", io.BytesIO(content), "text/plain"))],
    )
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]

    deadline = time.monotonic() + _POLL_TIMEOUT
    while time.monotonic() < deadline:
        r = _get(f"/runs/{run_id}")
        assert r.status_code == 200
        run = r.json()
        if run["status"] in ("completed", "failed"):
            break
        time.sleep(_POLL_INTERVAL)

    return run_id


@_SKIP_REVIEW
def test_get_review_for_unknown_run_returns_404():
    missing = str(uuid.uuid4())
    resp = _get(f"/runs/{missing}/review")
    assert resp.status_code == 404


@_SKIP_REVIEW
def test_review_workflow_entity_accept():
    """Accept a synthetic entity on a real run via the review endpoints."""
    run_id = _upload_and_wait()

    # Get the review summary for the run (should be empty initially)
    resp = _get(f"/runs/{run_id}/review")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["entity_reviews"] == []

    # Accept a synthetic entity (entity_id does not need to match real ProcessIR)
    resp = _post(
        "/reviews/entities/smoke-entity-1",
        json={
            "run_id": run_id,
            "entity_type": "workflow_step",
            "review_state": "accepted",
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert "id" in result
    assert result["data"]["review_state"] == "accepted"

    # Confirm the review is retrievable
    resp = _get(f"/runs/{run_id}/review")
    assert resp.status_code == 200
    reviews = resp.json()["entity_reviews"]
    assert any(r["entity_id"] == "smoke-entity-1" for r in reviews)


@_SKIP_REVIEW
def test_review_workflow_entity_edit():
    """Edit a synthetic entity label."""
    run_id = _upload_and_wait()

    resp = _post(
        "/reviews/entities/smoke-edit-entity",
        json={
            "run_id": run_id,
            "entity_type": "role",
            "review_state": "edited",
            "edited_label": "Revised Role Name",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["review_state"] == "edited"


@_SKIP_REVIEW
def test_review_workflow_relation_accept():
    """Accept a synthetic relation."""
    run_id = _upload_and_wait()

    resp = _post(
        "/reviews/relations/smoke-rel-1",
        json={
            "run_id": run_id,
            "relation_type": "performed_by",
            "source_entity_id": "step-1",
            "target_entity_id": "role-1",
            "review_state": "accepted",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["review_state"] == "accepted"


@_SKIP_REVIEW
def test_review_workflow_taxonomy_feedback():
    """Submit taxonomy feedback for a synthetic entity."""
    run_id = _upload_and_wait()

    resp = _post(
        "/reviews/taxonomy",
        json={
            "run_id": run_id,
            "entity_type": "workflow_step",
            "entity_id": "step-1",
            "feedback_type": "new_label",
            "proposed_label": "Better Step Name",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["feedback_type"] == "new_label"


@_SKIP_REVIEW
def test_invalid_review_state_rejected():
    run_id = _upload_and_wait()
    resp = _post(
        "/reviews/entities/some-entity",
        json={
            "run_id": run_id,
            "entity_type": "workflow_step",
            "review_state": "not_a_valid_state",
        },
    )
    assert resp.status_code == 422
