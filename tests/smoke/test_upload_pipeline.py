"""Smoke test: full upload-to-parsed-artifact pipeline.

Requires the full docker-compose stack to be running:
    docker compose up -d

Run with:
    pytest tests/smoke/test_upload_pipeline.py -v
"""

import io
import os
import time

import requests

BASE_URL = os.environ.get("SMOKE_API_URL", "http://localhost:8010")
_POLL_INTERVAL = 2  # seconds
_POLL_TIMEOUT = 60  # seconds


def _get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", **kwargs)


def _post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", **kwargs)


def test_health():
    resp = _get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready():
    resp = _get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_upload_pipeline():
    # Upload a small text artifact
    content = b"process: order-to-cash\nsteps: receive, validate, ship, invoice"
    resp = _post(
        "/runs/upload",
        files={"file": ("test_process.txt", io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    run_id = body["run_id"]
    assert body["status"] == "uploaded"
    assert body["object_uri"].startswith("minio://")
    assert body["source_id"]
    assert body["artifact_id"]

    # Poll until the run reaches a terminal state
    deadline = time.monotonic() + _POLL_TIMEOUT
    final_status = None
    while time.monotonic() < deadline:
        status_resp = _get(f"/runs/{run_id}")
        assert status_resp.status_code == 200, status_resp.text
        run = status_resp.json()
        if run["status"] in ("completed", "failed"):
            final_status = run["status"]
            break
        time.sleep(_POLL_INTERVAL)

    assert (
        final_status is not None
    ), f"Run {run_id} did not reach a terminal state within {_POLL_TIMEOUT}s"
    assert final_status == "completed", f"Run {run_id} ended in '{final_status}'"

    # Verify at least one parsed artifact was created
    run_detail = _get(f"/runs/{run_id}").json()
    artifact_types = [a["artifact_type"] for a in run_detail.get("artifacts", [])]
    assert (
        "parsed" in artifact_types
    ), f"Expected a 'parsed' artifact, got: {artifact_types}"
