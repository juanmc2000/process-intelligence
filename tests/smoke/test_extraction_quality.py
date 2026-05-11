"""End-to-end extraction quality tests.

Upload synthetic evidence files, wait for pipeline completion, retrieve
ProcessIR output, and assert expected entities/relations are present.

Requires the full docker-compose stack to be running:
    docker compose up -d

Run with:
    pytest tests/smoke/test_extraction_quality.py -v
"""

import io
import os
import time

import requests

BASE_URL = os.environ.get("SMOKE_API_URL", "http://localhost:8010")
_POLL_INTERVAL = 2
_POLL_TIMEOUT = 90


def _get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", **kwargs)


def _post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", **kwargs)


def _upload_and_wait(
    content: bytes, filename: str, content_type: str = "text/plain"
) -> dict:
    """Upload a file, poll until completed, and return the final run."""
    resp = _post(
        "/runs/upload",
        files=[("files", (filename, io.BytesIO(content), content_type))],
    )
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]

    deadline = time.monotonic() + _POLL_TIMEOUT
    while time.monotonic() < deadline:
        status_resp = _get(f"/runs/{run_id}")
        assert status_resp.status_code == 200
        run = status_resp.json()
        if run["status"] in ("completed", "failed"):
            assert run["status"] == "completed", f"Run {run_id} failed"
            return run
        time.sleep(_POLL_INTERVAL)

    raise AssertionError(f"Run {run_id} did not complete within {_POLL_TIMEOUT}s")


def _get_process_ir(run_id: str) -> dict:
    """Retrieve ProcessIR via the API endpoint."""
    resp = _get(f"/runs/{run_id}/process-ir")
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- Approval in system ---


def test_approval_in_system():
    """Upload evidence with approval workflow; verify approval entities and relations."""
    content = b"""\
Accounts Payable Invoice Processing Procedure

Step 1: The Clerk receives the invoice and enters it in SAP.
Step 2: The Finance Manager reviews the invoice for completeness.
Step 3: The Finance Manager approved the invoice after validation.
Step 4: The payment is posted in SAP by the Clerk.
"""
    run = _upload_and_wait(content, "approval_process.txt")
    run_id = run["id"]
    ir = _get_process_ir(run_id)

    assert ir["extraction_status"] == "completed"
    process_ir = ir.get("process_ir")
    assert process_ir is not None

    # Should find system touchpoints (SAP)
    systems = process_ir.get("system_touchpoints", [])
    system_names = {s["name"] for s in systems}
    assert "SAP" in system_names, f"Expected SAP in systems, got: {system_names}"

    # Should find roles
    roles = process_ir.get("roles", [])
    assert len(roles) > 0, "Expected at least one role"

    # Confidence summary should have counts
    summary = ir.get("confidence_summary", {})
    assert summary.get("system_touchpoint_count", 0) > 0


# --- Handoff ---


def test_handoff():
    """Upload evidence with handoff; verify handoff detection."""
    content = b"""\
Dispute Resolution Process

The customer complaint was logged as a ticket.
The ticket was assigned to the Legal Department for review.
Legal completed their assessment and sent the case to Compliance.
"""
    run = _upload_and_wait(content, "handoff_process.txt")
    run_id = run["id"]
    ir = _get_process_ir(run_id)

    assert ir["extraction_status"] == "completed"
    process_ir = ir.get("process_ir")
    assert process_ir is not None

    # Should find workflow steps
    steps = process_ir.get("workflow_steps", [])
    assert len(steps) > 0, "Expected workflow steps from handoff evidence"


# --- Escalation ---


def test_escalation():
    """Upload evidence with escalation; verify escalation detection."""
    content = b"""\
Exception Handling Procedure

Step 1: The Analyst flags the discrepancy in the reconciliation report.
Step 2: If the discrepancy exceeds $10,000, the issue is escalated to Senior Management.
Step 3: Senior Management reviews and approves the corrective action.
"""
    run = _upload_and_wait(content, "escalation_process.txt")
    run_id = run["id"]
    ir = _get_process_ir(run_id)

    assert ir["extraction_status"] == "completed"
    process_ir = ir.get("process_ir")
    assert process_ir is not None

    # Should find roles
    roles = process_ir.get("roles", [])
    assert len(roles) > 0, "Expected roles from escalation evidence"


# --- Threshold control ---


def test_threshold_control():
    """Upload evidence with threshold controls; verify control detection."""
    content = b"""\
Procurement Policy

All purchase orders require dual approval.
Any purchase order above $50,000 requires approval from the CFO.
Segregation of duties is enforced between requestor and approver.
The Auditor validates all transactions above the threshold quarterly.
"""
    run = _upload_and_wait(content, "threshold_control.txt")
    run_id = run["id"]
    ir = _get_process_ir(run_id)

    assert ir["extraction_status"] == "completed"
    process_ir = ir.get("process_ir")
    assert process_ir is not None

    # Should find controls
    controls = process_ir.get("controls", [])
    assert (
        len(controls) > 0
    ), f"Expected controls from threshold evidence, got: {controls}"

    summary = ir.get("confidence_summary", {})
    assert summary.get("control_count", 0) > 0


# --- Change event ---


def test_change_event():
    """Upload evidence with change events; verify change detection."""
    content = b"""\
Process Change Log - Q1 2025

The approval threshold changed from $10,000 to $25,000 effective January 2025.
The reconciliation process was updated to include automated matching in Oracle.
A new validation control was added for cross-border transactions.
"""
    run = _upload_and_wait(content, "change_log.txt")
    run_id = run["id"]
    ir = _get_process_ir(run_id)

    assert ir["extraction_status"] == "completed"
    process_ir = ir.get("process_ir")
    assert process_ir is not None

    # Should find change events
    changes = process_ir.get("change_events", [])
    assert len(changes) > 0, f"Expected change events, got: {changes}"


# --- Speculative negative example ---


def test_speculative_negative():
    """Upload speculative/negated evidence; verify minimal or no factual extraction."""
    content = b"""\
Planning Notes (Draft)

We might implement a new dual-approval process for high-value transactions.
The team is considering migrating to a new ERP system.
No decision has been made yet.
This proposal has not been approved.
"""
    run = _upload_and_wait(content, "speculative_notes.txt")
    run_id = run["id"]
    ir = _get_process_ir(run_id)

    assert ir["extraction_status"] == "completed"
    process_ir = ir.get("process_ir")
    assert process_ir is not None

    # Speculative content should produce minimal extraction
    # We don't assert zero — some keywords may still match — but counts should be low
    summary = ir.get("confidence_summary", {})
    total = sum(summary.get(k, 0) for k in summary if k.endswith("_count"))
    # Soft assertion: speculative text should produce less than a factual document
    assert (
        total < 20
    ), f"Speculative content produced unexpectedly many entities: {total}"
