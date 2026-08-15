from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HELPER_PATH = Path(__file__).parents[1] / "postgres_runtime_credentials.py"
SPEC = importlib.util.spec_from_file_location("postgres_runtime_credentials", HELPER_PATH)
assert SPEC and SPEC.loader
credentials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(credentials)


def test_runtime_table_allowlist_matches_canonical_schema() -> None:
    schema_path = Path(__file__).parents[3] / "backend/app/sql/schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    schema_tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", schema))

    assert set(credentials.RUNTIME_TABLES) == schema_tables


def test_provision_sql_grants_only_required_runtime_access() -> None:
    sql = credentials.build_provision_sql(
        "order_resolution",
        "order_resolution_runtime",
        "Password!with'quote",
        "pgadmin",
    )

    assert "NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT NOBYPASSRLS" in sql
    assert 'REASSIGN OWNED BY "order_resolution_runtime" TO "pgadmin"' in sql
    assert "Runtime schema objects must be owned by the administrator role." in sql
    assert "pg_get_userbyid(object.relowner) <> 'pgadmin'" in sql
    assert 'REVOKE TEMPORARY ON DATABASE "order_resolution" FROM PUBLIC' in sql
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC" in sql
    assert 'public."workflow_runs"' in sql
    assert 'public."memory_items"' in sql
    assert 'public."rag_retrieval_results"' in sql
    assert 'public."eval_results" TO "order_resolution_runtime"' in sql
    assert 'GRANT USAGE ON SEQUENCE public."conversation_messages_id_seq"' in sql
    assert "ON ALL TABLES IN SCHEMA public TO" not in sql
    assert "ON ALL SEQUENCES IN SCHEMA public TO" not in sql


def test_runtime_url_encodes_secret_and_requires_tls() -> None:
    url = credentials.build_runtime_url(
        "order_resolution",
        "order_resolution_runtime",
        "Password!/@:? #",
        "server.postgres.database.azure.com",
    )

    parsed = urlsplit(url)
    assert parsed.scheme == "postgresql+psycopg"
    assert parsed.hostname == "server.postgres.database.azure.com"
    assert unquote(parsed.username or "") == "order_resolution_runtime"
    assert unquote(parsed.password or "") == "Password!/@:? #"
    assert unquote(parsed.path.lstrip("/")) == "order_resolution"
    assert parse_qs(parsed.query) == {"sslmode": ["require"]}


def test_verification_rejects_ownership_and_extra_privileges() -> None:
    sql = credentials.build_verification_sql("order_resolution_runtime")

    assert "object.relowner" in sql
    assert "has_database_privilege(current_user, current_database(), 'TEMPORARY')" in sql
    assert "has_schema_privilege(current_user, 'public', 'CREATE')" in sql
    assert "public.memory_items', 'TRUNCATE'" in sql
    assert "public.conversation_messages_id_seq', 'UPDATE'" in sql
    assert "CREATE TABLE public.__order_resolution_runtime_ddl_probe" in sql
    assert "CREATE ROLE __order_resolution_runtime_role_probe NOLOGIN" in sql
    assert "WHEN insufficient_privilege THEN NULL" in sql
