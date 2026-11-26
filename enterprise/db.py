"""PostgreSQL persistence for authenticated handoffs; this is not a Stripe ledger."""
from __future__ import annotations
import os

DDL = """
CREATE TABLE IF NOT EXISTS fulfillment_receipts (
  payment_reference VARCHAR(160) PRIMARY KEY,
  payload_sha256 CHAR(64) NOT NULL,
  amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
  currency CHAR(3) NOT NULL CHECK (currency = 'usd'),
  sku VARCHAR(100) NOT NULL,
  offer_name TEXT NOT NULL,
  customer_email TEXT NOT NULL,
  stripe_created_at TEXT NOT NULL,
  fulfill_hours INTEGER,
  processing_status TEXT NOT NULL DEFAULT 'RECEIVED_UNFULFILLED'
      CHECK (processing_status IN ('RECEIVED_UNFULFILLED', 'REVIEW_REQUIRED', 'FULFILLED')),
  received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

class PayloadConflict(Exception):
    pass

def _normalize_dsn(url: str) -> str:
    # Railway may provide SQLAlchemy driver syntax; psycopg.connect needs libpq URL syntax.
    # Normalize only the scheme. Do not log, quote, or otherwise expose credentials.
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url[len("postgresql+psycopg://"):]
    return url


def connect():
    import psycopg
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL unavailable")
    return psycopg.connect(_normalize_dsn(url), connect_timeout=5)

def migrate():
    with connect() as db:
        with db.cursor() as cur:
            cur.execute(DDL)

def check_ready():
    with connect() as db:
        with db.cursor() as cur:
            cur.execute("SELECT to_regclass('public.fulfillment_receipts')")
            return cur.fetchone()[0] is not None

def record_receipt(message: dict, digest: str) -> bool:
    """True if inserted; False for same-payload replay. Conflict never overwrites."""
    with connect() as db:
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO fulfillment_receipts
                   (payment_reference, payload_sha256, amount_minor, currency, sku,
                    offer_name, customer_email, stripe_created_at, fulfill_hours)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (payment_reference) DO NOTHING
                   RETURNING payment_reference""",
                (message["payment_reference"], digest, message["amount_minor"],
                 message["currency"], message["sku"], message["offer_name"],
                 message["customer_email"], message["created_at"], message["fulfill_hours"]),
            )
            if cur.fetchone() is not None:
                return True
            cur.execute(
                "SELECT payload_sha256 FROM fulfillment_receipts WHERE payment_reference = %s",
                (message["payment_reference"],),
            )
            row = cur.fetchone()
            if row and row[0] == digest:
                return False
            raise PayloadConflict("same payment reference, changed payload")
