from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest
from app.core.database import postgres_db


def _database_available() -> bool:
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/maf_workflow"
    )
    try:
        with psycopg.connect(database_url, connect_timeout=2):
            return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def ensure_database_available() -> Iterator[None]:
    if not _database_available():
        pytest.skip("PostgreSQL is required for backend tests in this repository.")
    postgres_db.ensure_schema()
    yield
    postgres_db.close()
