"""Smoke test: full upload-to-ProcessIR-extraction pipeline.

Requires the full docker-compose stack to be running:
    docker compose up -d

Run with:
    pytest tests/smoke/test_upload_pipeline.py -v

Or via make:
    make smoke
"""

import io
import os
import time

import requests

BASE_URL = os.environ.get("SMOKE_API_URL", "http://localhost:8010")
_POLL_INTERVAL = 2  # seconds
_POLL_TIMEOUT = 90  # seconds — Sprint 2 pipeline is longer (parse + extract)


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
    assert resp.json()["status"] in ("ok", "ready")


def test_run_not_found():
    resp = _get("/runs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_upload_pipeline():
    """End-to-end: upload → normalized evidence → ProcessIR extraction → completed."""
    content = b"process: order-to-cash\nsteps: receive, validate, ship, invoice"
    resp = _post(
        "/runs/upload",
        files=[("files", ("test_process.txt", io.BytesIO(content), "text/plain"))],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    run_id = body["run_id"]
    assert body["status"] == "uploaded"
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["object_uri"].startswith("minio://")
    assert source["source_id"]
    assert source["artifact_id"]

    # Poll until the run reaches a terminal state
    deadline = time.monotonic() + _POLL_TIMEOUT
    final_run = None
    while time.monotonic() < deadline:
        status_resp = _get(f"/runs/{run_id}")
        assert status_resp.status_code == 200, status_resp.text
        run = status_resp.json()
        if run["status"] in ("completed", "failed"):
            final_run = run
            break
        time.sleep(_POLL_INTERVAL)

    assert (
        final_run is not None
    ), f"Run {run_id} did not reach a terminal state within {_POLL_TIMEOUT}s"
    assert (
        final_run["status"] == "completed"
    ), f"Run {run_id} ended in '{final_run['status']}'"

    _assert_normalized_evidence_artifact(run_id, final_run)
    _assert_process_ir_artifact(run_id, final_run)
    _assert_extraction_summary(run_id, final_run)
    _assert_no_raw_customer_content(final_run)


def test_multi_file_upload():
    """Multi-file upload creates one run and one source/artifact per file."""
    file_a = b"process: order-to-cash\nsteps: receive, validate, ship, invoice"
    file_b = b"process: invoice-to-pay\nsteps: receive, approve, pay"
    resp = _post(
        "/runs/upload",
        files=[
            ("files", ("process_a.txt", io.BytesIO(file_a), "text/plain")),
            ("files", ("process_b.txt", io.BytesIO(file_b), "text/plain")),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["status"] == "uploaded"
    assert "run_id" in body
    assert len(body["sources"]) == 2

    filenames = {s["filename"] for s in body["sources"]}
    assert "process_a.txt" in filenames
    assert "process_b.txt" in filenames

    for source in body["sources"]:
        assert source["source_id"]
        assert source["artifact_id"]
        assert source["object_uri"].startswith("minio://")


def test_empty_upload_rejected():
    """POST /runs/upload with no files returns 422."""
    resp = _post("/runs/upload", files=[])
    assert resp.status_code == 422


def _assert_normalized_evidence_artifact(run_id: str, run: dict) -> None:
    """Confirm a normalized_evidence artifact was created."""
    artifact_types = [a["artifact_type"] for a in run.get("artifacts", [])]
    assert (
        "normalized_evidence" in artifact_types
    ), f"Expected a 'normalized_evidence' artifact for run {run_id}, got: {artifact_types}"
    ne_artifacts = [
        a for a in run["artifacts"] if a["artifact_type"] == "normalized_evidence"
    ]
    assert len(ne_artifacts) >= 1
    ne = ne_artifacts[0]
    assert ne["object_uri"].startswith("minio://")
    assert ne["deletion_eligible"] is True


def _assert_process_ir_artifact(run_id: str, run: dict) -> None:
    """Confirm a process_ir artifact was created and is marked durable."""
    artifact_types = [a["artifact_type"] for a in run.get("artifacts", [])]
    assert (
        "process_ir" in artifact_types
    ), f"Expected a 'process_ir' artifact for run {run_id}, got: {artifact_types}"
    ir_artifacts = [a for a in run["artifacts"] if a["artifact_type"] == "process_ir"]
    assert len(ir_artifacts) >= 1
    ir = ir_artifacts[0]
    assert ir["object_uri"].startswith("minio://")
    assert ir["deletion_eligible"] is False


def _assert_extraction_summary(run_id: str, run: dict) -> None:
    """Confirm extraction summary is present and contains a ProcessIR URI."""
    extraction = run.get("extraction")
    assert extraction is not None, f"Run {run_id} response missing 'extraction' field"
    assert (
        extraction["status"] == "completed"
    ), f"Expected extraction status 'completed', got '{extraction['status']}'"
    assert (
        extraction["process_ir_uri"] is not None
    ), f"Run {run_id} extraction has no process_ir_uri"
    assert extraction["process_ir_uri"].startswith("minio://")
    assert extraction["extraction_run_id"] is not None


def _assert_no_raw_customer_content(run: dict) -> None:
    """Confirm no raw customer content appears in the API response."""
    run_str = str(run)
    forbidden_fragments = [
        "order-to-cash",  # the actual content from the uploaded file
        "receive, validate, ship, invoice",
        "parsed_text",
    ]
    for fragment in forbidden_fragments:
        assert (
            fragment not in run_str
        ), f"Raw customer content found in API response: '{fragment}'"
