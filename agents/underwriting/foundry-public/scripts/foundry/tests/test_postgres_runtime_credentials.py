from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import DBAPIError

BACKEND_PATH = Path(__file__).parents[3] / "backend"
sys.path.insert(0, str(BACKEND_PATH))
HELPER_PATH = Path(__file__).parents[1] / "postgres_runtime_credentials.py"
SPEC = importlib.util.spec_from_file_location("postgres_runtime_credentials", HELPER_PATH)
assert SPEC and SPEC.loader
credentials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(credentials)
DDL_PATH = Path(__file__).parents[1] / "generate_postgres_schema_ddl.py"
DDL_SPEC = importlib.util.spec_from_file_location("generate_postgres_schema_ddl", DDL_PATH)
assert DDL_SPEC and DDL_SPEC.loader
schema_ddl = importlib.util.module_from_spec(DDL_SPEC)
DDL_SPEC.loader.exec_module(schema_ddl)
from app.infrastructure.db.tables import metadata  # noqa: E402


class PostgresRuntimeCredentialTests(unittest.TestCase):
    def test_provision_sql_grants_only_runtime_objects(self) -> None:
        sql = credentials.build_provision_sql(
            "underwriting",
            "underwriting_runtime",
            "Password!with'quote",
            "pgadmin",
        )

        self.assertIn("NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT NOBYPASSRLS", sql)
        self.assertIn('REASSIGN OWNED BY "underwriting_runtime" TO "pgadmin"', sql)
        self.assertIn('DROP OWNED BY "underwriting_runtime"', sql)
        self.assertIn("REVOKE CREATE ON SCHEMA public FROM PUBLIC", sql)
        self.assertIn('GRANT USAGE ON SCHEMA public TO "underwriting_runtime"', sql)
        self.assertNotIn("GRANT USAGE, CREATE ON SCHEMA", sql)
        self.assertNotIn("GRANT CONNECT, CREATE", sql)
        self.assertNotIn("ON ALL TABLES IN SCHEMA public TO", sql)
        self.assertNotIn("ON ALL SEQUENCES IN SCHEMA public TO", sql)
        self.assertIn(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public."workflow_runs"',
            sql,
        )
        self.assertIn('public."maf_checkpoints"', sql)
        self.assertIn('public."underwriting_approvals"', sql)
        self.assertIn('public."teams_card_actions" TO "underwriting_runtime"', sql)
        self.assertIn('GRANT USAGE ON SEQUENCE public."business_state_id_seq"', sql)
        self.assertNotIn("GRANT USAGE, SELECT, UPDATE ON SEQUENCE", sql)

    def test_runtime_url_encodes_credential_and_requires_tls(self) -> None:
        url = credentials.build_runtime_url(
            "underwriting",
            "underwriting_runtime",
            "Password!/@:? #",
            "server.postgres.database.azure.com",
        )
        parsed = urlsplit(url)

        self.assertEqual(parsed.scheme, "postgresql+psycopg")
        self.assertEqual(parsed.hostname, "server.postgres.database.azure.com")
        self.assertEqual(unquote(parsed.username or ""), "underwriting_runtime")
        self.assertEqual(unquote(parsed.password or ""), "Password!/@:? #")
        self.assertEqual(unquote(parsed.path.lstrip("/")), "underwriting")
        self.assertEqual(parse_qs(parsed.query), {"sslmode": ["require"]})

    def test_verification_checks_runtime_access_and_admin_denial(self) -> None:
        sql = credentials.build_verification_sql("underwriting_runtime")

        self.assertIn("PERFORM 1 FROM public.workflow_runs LIMIT 1", sql)
        self.assertIn("CREATE TABLE public.__underwriting_runtime_ddl_probe", sql)
        self.assertIn("CREATE ROLE __underwriting_runtime_role_probe NOLOGIN", sql)
        self.assertIn("WHEN insufficient_privilege THEN NULL", sql)
        self.assertIn("has_table_privilege(current_user, 'public.workflow_events', 'DELETE')", sql)
        self.assertIn(
            "has_sequence_privilege(current_user, 'public.maf_checkpoints_id_seq', 'USAGE')",
            sql,
        )
        self.assertIn(
            "has_table_privilege(current_user, 'public.underwriting_approvals', 'DELETE')",
            sql,
        )
        self.assertIn(
            "has_table_privilege(current_user, 'public.teams_card_actions', 'DELETE')",
            sql,
        )
        self.assertIn("Runtime credential has privileges on a non-runtime table", sql)
        self.assertIn("Runtime credential has privileges on a non-runtime sequence", sql)

    def test_runtime_allowlists_match_schema_metadata(self) -> None:
        self.assertEqual(set(credentials.RUNTIME_TABLES), set(metadata.tables))
        sequence_tables = {
            table.name
            for table in metadata.sorted_tables
            if any(
                column.primary_key
                and column.autoincrement is not False
                and str(column.type).upper() == "INTEGER"
                for column in table.columns
            )
        }
        self.assertEqual(
            set(credentials.RUNTIME_SEQUENCES),
            {f"{table_name}_id_seq" for table_name in sequence_tables},
        )

    def test_checkpoint_unique_constraint_precedes_foreign_key_tables(self) -> None:
        sql = schema_ddl.build_ddl()
        constraint_position = sql.index(
            "ADD CONSTRAINT uq_maf_checkpoints_checkpoint_id UNIQUE (checkpoint_id)"
        )

        self.assertLess(
            constraint_position,
            sql.index("CREATE TABLE IF NOT EXISTS teams_card_actions"),
        )
        self.assertLess(
            constraint_position,
            sql.index("CREATE TABLE IF NOT EXISTS underwriting_approvals"),
        )

    @unittest.skipUnless(
        os.getenv("UNDERWRITING_TEST_POSTGRES_URL"),
        "UNDERWRITING_TEST_POSTGRES_URL is required for the real grant test",
    )
    def test_real_postgres_grants_are_required_and_exact(self) -> None:
        admin_url = make_url(os.environ["UNDERWRITING_TEST_POSTGRES_URL"])
        database = admin_url.database or ""
        role = f"uw_runtime_{uuid4().hex[:8]}"
        password = f"Runtime-{uuid4().hex}!42"
        admin_engine = create_engine(admin_url, future=True)
        runtime_engine = None
        metadata.create_all(admin_engine)
        try:
            with admin_engine.begin() as conn:
                admin_username = str(conn.execute(text("SELECT current_user")).scalar_one())
                conn.execute(text("CREATE TABLE IF NOT EXISTS runtime_grant_probe (id integer)"))
                conn.exec_driver_sql(
                    credentials.build_provision_sql(
                        database,
                        role,
                        password,
                        admin_username,
                    ).replace("%", "%%")
                )

            runtime_url = admin_url.set(username=role, password=password)
            runtime_engine = create_engine(runtime_url, future=True)
            with runtime_engine.begin() as conn:
                conn.exec_driver_sql(
                    credentials.build_verification_sql(role).replace("%", "%%")
                )

            with admin_engine.begin() as conn:
                conn.execute(text(f'GRANT SELECT ON runtime_grant_probe TO "{role}"'))
            with self.assertRaises(DBAPIError):
                with runtime_engine.begin() as conn:
                    conn.exec_driver_sql(
                        credentials.build_verification_sql(role).replace("%", "%%")
                    )
        finally:
            if runtime_engine is not None:
                runtime_engine.dispose()
            with admin_engine.begin() as conn:
                conn.execute(
                    text(
                        f'DO $cleanup$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles '
                        f"WHERE rolname = '{role}') THEN "
                        f'EXECUTE \'DROP OWNED BY "{role}"\'; '
                        f'EXECUTE \'DROP ROLE "{role}"\'; '
                        "END IF; END $cleanup$"
                    )
                )
                conn.execute(text("DROP TABLE IF EXISTS runtime_grant_probe"))
            metadata.drop_all(admin_engine)
            admin_engine.dispose()


if __name__ == "__main__":
    unittest.main()
