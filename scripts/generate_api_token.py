"""Generate a high-entropy API bearer token locally for Vault storage.

Run this script in a trusted local terminal. Copy its output directly into the
Vault KV v2 value API_BEARER_TOKEN; never commit or paste the generated token.
"""
from __future__ import annotations

import secrets


def main() -> int:
    print(secrets.token_urlsafe(48))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
