"""Parser worker: registers the ingestion workflow and activities with Temporal."""

import asyncio
import logging

from temporalio.worker import Worker

from packages.core.workflows import (
    IngestionRunWorkflow,
    _complete_run,
    _fail_run,
    extract_process_ir,
    make_temporal_client,
    parse_artifact,
    update_run_to_processing,
)
from packages.core.workflows.ingestion import TASK_QUEUE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    client = await make_temporal_client()
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[IngestionRunWorkflow],
        activities=[
            update_run_to_processing,
            parse_artifact,
            extract_process_ir,
            _complete_run,
            _fail_run,
        ],
    )
    logger.info("Parser worker starting on task queue '%s'", TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
