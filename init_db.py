"""Run versioned PostgreSQL/pgvector migrations before the API starts."""
from __future__ import annotations

import logging
import os
import random
import time
from pathlib import Path

import psycopg

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("garcar.migrations")
MIGRATION_VERSION = "001_governance_core"
MIGRATION_FILE = Path(__file__).parent / "src" / "governance" / "migrations" / "001_governance_core.sql"


def run_migrations() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required when ENABLE_GOVERNANCE_DB=true")
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
            log.info("Connecting to PostgreSQL (attempt %s/%s)", attempt, retries)
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
                # Serialize migration runners across replicas.
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (734_991_202_610_31,))
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS enterprise_schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                """)
                cur.execute("SELECT 1 FROM enterprise_schema_migrations WHERE version = %s", (MIGRATION_VERSION,))
                if cur.fetchone():
                    log.info("Migration %s already applied", MIGRATION_VERSION)
                    return
                # psycopg 3's simple-query mode permits the migration's ordered DDL statements.
                cur.execute(migration_sql, prepare=False)
                cur.execute("INSERT INTO enterprise_schema_migrations(version) VALUES (%s)", (MIGRATION_VERSION,))
        log.info("Migration %s applied successfully", MIGRATION_VERSION)
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()
