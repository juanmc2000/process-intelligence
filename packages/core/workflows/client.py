import os

from temporalio.client import Client


async def make_temporal_client() -> Client:
    """Connect to Temporal from environment variables.

    Required env vars:
        TEMPORAL_HOST  host:port of the Temporal frontend (e.g. temporal:7233)
    Optional:
        TEMPORAL_NAMESPACE  Temporal namespace (default: default)
    """
    host = os.environ.get("TEMPORAL_HOST", "temporal:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    return await Client.connect(host, namespace=namespace)
