"""Run versioned PostgreSQL/pgvector migrations before the API starts."""
from __future__ import annotations

import logging
import os
import random
import time
from pathlib import Path

import psycopg
from psycopg import sql

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("garcar.migrations")
MIGRATION_VERSION = "001_governance_core"
MIGRATION_FILE = Path(__file__).parent / "src" / "governance" / "migrations" / "001_governance_core.sql"


def _provision_runtime_role(cur: psycopg.Cursor) -> None:
    """Give the API a separate least-privilege role; migration credentials stay out of the app."""
    role = os.getenv("GARCAR_RUNTIME_DB_USER", "").strip()
    password = os.getenv("GARCAR_RUNTIME_DB_PASSWORD", "")
    if not role and not password:
        return
    if not role or not password or len(password) < 32:
        raise RuntimeError("Runtime DB role requires GARCAR_RUNTIME_DB_USER and a password of at least 32 characters")

    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    role_exists = cur.fetchone() is not None
    cur.execute(
        "SELECT parent.rolname FROM pg_auth_members m "
        "JOIN pg_roles parent ON parent.oid = m.roleid "
        "JOIN pg_roles member ON member.oid = m.member "
        "WHERE member.rolname = %s",
        (role,),
    )
    memberships = cur.fetchall()
    if memberships:
        raise RuntimeError("Runtime DB role must not inherit privileges from other PostgreSQL roles")

    statement = (
        "ALTER ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
        if role_exists
        else "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
    )
    cur.execute(sql.SQL(statement).format(sql.Identifier(role), sql.Literal(password)))
    cur.execute("SELECT current_database()")
    database_name = cur.fetchone()[0]
    cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
        sql.Identifier(database_name), sql.Identifier(role)
    ))
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))

    # Remove stale or overly broad grants on an existing runtime role before applying
    # the exact allow-list. Do not grant default privileges on future tables.
    cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {}").format(
        sql.Identifier(role)
    ))
    cur.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {}").format(
        sql.Identifier(role)
    ))
    cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(sql.Identifier(role)))

    grants = {
        "enterprise_proposals": "SELECT, INSERT, UPDATE",
        "enterprise_approvals": "SELECT, INSERT",
        "enterprise_execution_events": "SELECT, INSERT",
        "enterprise_audit_events": "SELECT, INSERT",
        "enterprise_vector_memory": "SELECT, INSERT",
        "enterprise_control_state": "SELECT, INSERT, UPDATE",
    }
    for table, privileges in grants.items():
        cur.execute(sql.SQL("GRANT " + privileges + " ON TABLE {} TO {}").format(
            sql.Identifier(table), sql.Identifier(role)
        ))

    for sequence in (
        "enterprise_approvals_approval_id_seq",
        "enterprise_execution_events_event_id_seq",
        "enterprise_audit_events_event_id_seq",
        "enterprise_vector_memory_id_seq",
    ):
        cur.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO {}").format(
            sql.Identifier(sequence), sql.Identifier(role)
        ))
    log.info("Provisioned least-privilege runtime database role %s", role)


def run_migrations() -> None:
    # Prefer a separate migration/admin URL; DATABASE_URL remains the runtime app identity.
    database_url = os.environ.get("MIGRATIONS_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("MIGRATIONS_DATABASE_URL (or DATABASE_URL for local development) is required")
    if not MIGRATION_FILE.is_file():
        raise RuntimeError(f"Migration file missing: {MIGRATION_FILE}")

    migration_sql = MIGRATION_FILE.read_text(encoding="utf-8")
    retries = int(os.getenv("DB_CONNECT_RETRIES", "10"))
    delay = float(os.getenv("DB_CONNECT_RETRY_DELAY_SECONDS", "3"))
    if retries < 1 or delay <= 0:
        raise ValueError("Database retry settings must be positive")

    conn = None
    for attempt in range(1, retries + 1):
        try:
            log.info("Connecting to PostgreSQL migrations endpoint (attempt %s/%s)", attempt, retries)
            conn = psycopg.connect(database_url, connect_timeout=5)
            break
        except psycopg.OperationalError:
            if attempt == retries:
                raise
            sleep_for = delay * min(attempt, 4) + random.uniform(0, 0.25)
            log.warning("Database unavailable; retrying in %.2fs", sleep_for)
            time.sleep(sleep_for)

    assert conn is not None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (734_991_202_610_31,))
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS enterprise_schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute("SELECT 1 FROM enterprise_schema_migrations WHERE version = %s", (MIGRATION_VERSION,))
                if not cur.fetchone():
                    # psycopg 3 simple-query mode permits ordered DDL in the migration.
                    cur.execute(migration_sql, prepare=False)
                    cur.execute("INSERT INTO enterprise_schema_migrations(version) VALUES (%s)", (MIGRATION_VERSION,))
                    log.info("Migration %s applied successfully", MIGRATION_VERSION)
                else:
                    log.info("Migration %s already applied", MIGRATION_VERSION)
                _provision_runtime_role(cur)
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()
