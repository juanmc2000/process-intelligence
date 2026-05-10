import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras


def _dsn() -> str:
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'postgres')} "
        f"port={os.environ.get('POSTGRES_INTERNAL_PORT', '5432')} "
        f"dbname={os.environ['POSTGRES_DB']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']}"
    )


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a psycopg2 connection and commit or rollback on exit."""
    conn = psycopg2.connect(_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
