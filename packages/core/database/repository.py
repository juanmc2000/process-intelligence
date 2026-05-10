"""Lightweight repository helpers for run, source, artifact, and event records.

All functions accept an open psycopg2 connection and execute SQL against it.
Callers control transaction boundaries via get_connection().
"""

from typing import Any, Optional
from uuid import UUID

import psycopg2.extensions


def create_run(
    conn: psycopg2.extensions.connection,
    status: str = "uploaded",
) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO runs (status) VALUES (%s) RETURNING id",
            (status,),
        )
        return cur.fetchone()["id"]


def update_run_status(
    conn: psycopg2.extensions.connection,
    run_id: UUID,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE runs
               SET status = %s,
                   error_message = %s,
                   updated_at = now()
             WHERE id = %s
            """,
            (status, error_message, str(run_id)),
        )


def create_source(
    conn: psycopg2.extensions.connection,
    run_id: UUID,
    filename: str,
    content_type: Optional[str] = None,
    size_bytes: Optional[int] = None,
    input_hash: Optional[str] = None,
    status: str = "uploaded",
) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sources
                (run_id, filename, content_type, size_bytes, input_hash, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (str(run_id), filename, content_type, size_bytes, input_hash, status),
        )
        return cur.fetchone()["id"]


def update_source_status(
    conn: psycopg2.extensions.connection,
    source_id: UUID,
    status: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sources SET status = %s, updated_at = now() WHERE id = %s",
            (status, str(source_id)),
        )


def create_artifact(
    conn: psycopg2.extensions.connection,
    run_id: UUID,
    artifact_type: str,
    object_uri: str,
    source_id: Optional[UUID] = None,
    content_type: Optional[str] = None,
    size_bytes: Optional[int] = None,
    schema_version: Optional[str] = None,
    deletion_eligible: bool = False,
) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO artifacts
                (run_id, source_id, artifact_type, object_uri,
                 content_type, size_bytes, schema_version, deletion_eligible)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(run_id),
                str(source_id) if source_id else None,
                artifact_type,
                object_uri,
                content_type,
                size_bytes,
                schema_version,
                deletion_eligible,
            ),
        )
        return cur.fetchone()["id"]


def create_workflow_event(
    conn: psycopg2.extensions.connection,
    run_id: UUID,
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
) -> UUID:
    import json

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO workflow_events (run_id, event_type, payload)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (
                str(run_id),
                event_type,
                json.dumps(payload) if payload else None,
            ),
        )
        return cur.fetchone()["id"]


def get_run(
    conn: psycopg2.extensions.connection,
    run_id: UUID,
) -> Optional[dict[str, Any]]:
    """Return run with linked sources, artifacts, and workflow_events, or None."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM runs WHERE id = %s", (str(run_id),))
        run = cur.fetchone()
        if run is None:
            return None

        cur.execute(
            "SELECT * FROM sources WHERE run_id = %s ORDER BY created_at",
            (str(run_id),),
        )
        sources = cur.fetchall()

        cur.execute(
            "SELECT * FROM artifacts WHERE run_id = %s ORDER BY created_at",
            (str(run_id),),
        )
        artifacts = cur.fetchall()

        cur.execute(
            "SELECT * FROM workflow_events WHERE run_id = %s ORDER BY created_at",
            (str(run_id),),
        )
        events = cur.fetchall()

    return {
        **dict(run),
        "sources": [dict(s) for s in sources],
        "artifacts": [dict(a) for a in artifacts],
        "workflow_events": [dict(e) for e in events],
    }
