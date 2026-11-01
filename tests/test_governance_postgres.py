"""Real PostgreSQL/pgvector migration and persistence checks; CI only."""
from __future__ import annotations
import os
import uuid
import psycopg
import pytest
from pgvector import Vector
from pgvector.psycopg import register_vector
from init_db import run_migrations

DATABASE_URL = os.environ["DATABASE_URL"]

@pytest.fixture(scope="module", autouse=True)
def migrated_database():
    run_migrations()
    run_migrations()
    yield

def test_pgvector_extension_and_hnsw_index_exist():
    with psycopg.connect(DATABASE_URL) as conn:
        assert conn.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone()
        assert conn.execute("SELECT 1 FROM pg_indexes WHERE indexname='idx_vector_memory_embedding'").fetchone()

def test_vector_memory_round_trip_and_cosine_search():
    namespace = "ci-" + uuid.uuid4().hex
    vector = Vector([1.0] + [0.0] * 1535)
    with psycopg.connect(DATABASE_URL) as conn:
        register_vector(conn)
        conn.execute(
            "INSERT INTO enterprise_vector_memory(namespace,content,metadata,embedding) VALUES (%s,%s,%s,%s)",
            (namespace, "integration-test-vector", "{}", vector),
        )
        row = conn.execute(
            """SELECT content, 1-(embedding <=> %s) AS similarity
               FROM enterprise_vector_memory WHERE namespace=%s
               ORDER BY embedding <=> %s LIMIT 1""",
            (vector, namespace, vector),
        ).fetchone()
    assert row is not None and row[0] == "integration-test-vector"
    assert float(row[1]) > 0.999

def test_audit_events_reject_update_and_delete():
    with psycopg.connect(DATABASE_URL) as conn:
        event_id = conn.execute(
            """INSERT INTO enterprise_audit_events(event_type,actor_id,event_data,event_hash)
               VALUES ('CI_IMMUTABILITY_TEST','ci','{}',%s) RETURNING event_id""",
            (uuid.uuid4().hex.ljust(64, "0"),),
        ).fetchone()[0]
        conn.commit()
        with pytest.raises(psycopg.Error, match="append-only"):
            with conn.transaction():
                conn.execute("UPDATE enterprise_audit_events SET actor_id='tampered' WHERE event_id=%s", (event_id,))
        with pytest.raises(psycopg.Error, match="append-only"):
            with conn.transaction():
                conn.execute("DELETE FROM enterprise_audit_events WHERE event_id=%s", (event_id,))
