"""Ingestion run workflow: uploaded → processing → completed | failed."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from packages.core.workflows.activities import (
        ExtractInput,
        ParseInput,
        extract_process_ir,
        parse_artifact,
        update_run_to_processing,
    )


TASK_QUEUE = "ingestion"

_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))


@workflow.defn(name="IngestionRunWorkflow")
class IngestionRunWorkflow:
    @workflow.run
    async def run(self, run_id: str, source_id: str, artifact_uri: str) -> str:
        """Orchestrate the ingestion pipeline for a single uploaded artifact.

        Status transitions persisted in Postgres:
            uploaded → processing → completed | failed

        Pipeline steps:
            1. update_run_to_processing
            2. parse_artifact  → normalized evidence artifact
            3. extract_process_ir  → ProcessIR artifact (deterministic stub)
            4. complete_run
        """

        await workflow.execute_activity(
            update_run_to_processing,
            run_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )

        try:
            parse_result: dict = await workflow.execute_activity(
                parse_artifact,
                ParseInput(
                    run_id=run_id, source_id=source_id, artifact_uri=artifact_uri
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=_RETRY,
            )

            await workflow.execute_activity(
                extract_process_ir,
                ExtractInput(
                    run_id=run_id,
                    normalized_evidence_uri=parse_result["normalized_evidence_uri"],
                    normalized_evidence_id=parse_result["normalized_evidence_id"],
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=_RETRY,
            )

        except Exception as exc:
            await workflow.execute_activity(
                _fail_run,
                FailInput(run_id=run_id, error=str(exc)),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            raise

        await workflow.execute_activity(
            _complete_run,
            run_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_RETRY,
        )
        return parse_result["normalized_evidence_uri"]


# ---------------------------------------------------------------------------
# Terminal status activities (inline — keep the module self-contained)
# ---------------------------------------------------------------------------

from dataclasses import dataclass  # noqa: E402

from temporalio import activity  # noqa: E402


@dataclass
class FailInput:
    run_id: str
    error: str


@activity.defn(name="complete_run")
async def _complete_run(run_id: str) -> None:
    from uuid import UUID

    from packages.core.database.repository import (
        create_workflow_event,
        update_run_status,
    )
    from packages.core.database.session import get_connection

    with get_connection() as conn:
        update_run_status(conn, UUID(run_id), "completed")
        create_workflow_event(conn, UUID(run_id), "completed")
    activity.logger.info("Run %s completed", run_id)


@activity.defn(name="fail_run")
async def _fail_run(inp: FailInput) -> None:
    from uuid import UUID

    from packages.core.database.repository import (
        create_workflow_event,
        update_run_status,
    )
    from packages.core.database.session import get_connection

    with get_connection() as conn:
        update_run_status(conn, UUID(inp.run_id), "failed", error_message=inp.error)
        create_workflow_event(conn, UUID(inp.run_id), "failed", {"error": inp.error})
    activity.logger.error("Run %s failed: %s", inp.run_id, inp.error)
