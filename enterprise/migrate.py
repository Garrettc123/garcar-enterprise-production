"""Idempotent PostgreSQL schema setup, without credential-bearing error traces."""
from __future__ import annotations

import sys
from .db import migrate


def main() -> int:
    try:
        migrate()
    except Exception:
        # Database connection exceptions may embed the full DATABASE_URL.
        # Never log exception text, cause, or traceback in deployment output.
        print("fulfillment migration blocked: database schema/connectivity check failed",
              file=sys.stderr)
        return 1
    print("fulfillment receipts schema ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
