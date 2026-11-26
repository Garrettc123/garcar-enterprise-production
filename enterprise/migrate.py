"""Idempotent PostgreSQL schema setup; invokes only the linked staging database."""
from .db import migrate

if __name__ == "__main__":
    migrate()
    print("fulfillment receipts schema ready")
