"""Pre-send deliverability suppression: evidence from Gmail failure notices.

Only known failed recipient hashes are embedded; no recipient addresses are
published in source. A suppression is a hold pending re-verification, not a
claim that a person/company is permanently unreachable.
Additional operator-approved suppressions may be supplied by environment.
This guard is in addition to (not a replacement for) the GAR-530 approval gate.
"""
from __future__ import annotations

import hashlib
import os
import re

_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+[.][A-Za-z]{2,}$")

# Nine unique recipient addresses from Gmail delivery-failure notifications
# dated 2026-10-29 through 2026-11-22. Duplicate failures are counted once.
# SHA-256 of lowercase, stripped UTF-8 address; no raw contacts in the repo.
_FAILED_RECIPIENT_HASHES = frozenset({
    "347839b8911e83a086e16d78019dad5e00c38b1dc3ef9e2bf836d28aef0d3921",
    "561bdd421a4f4725e5181fccb853e3df30c4a425fdc90d076858bc3b93e27eeb",
    "6d8f8934bd58462f66e7348b022aca7781ceef6dd1c5cbfd96f1c3d993340e18",
    "8c38d150dd654371d866c6b38d116aef9d9fe24d89f02182a68f505c845e4bfa",
    "9502cff0b62152447eaf03ceaceda3a6b9de3a43520e083ec0761e6b28a7a75e",
    "4c9a9c82390134ebcb87da9b73b67d94f076846175123d60acaadbde3b701ad7",
    "9f50541c8953bd39da26a037aa4cdca1458f281ccb469fb33b44b020771f1239",
    "66067c573b4da0687de878bcb940af42566732e8c3c2744a33898d93872ca4ba",
    "25cee2b5ad1c2a3825f5d821ed3431ce1fbac861fb7dd9a003d6b1772c238de1",
})


def _csv_env(name: str) -> set[str]:
    return {part.strip().casefold() for part in os.getenv(name, "").split(",") if part.strip()}


def suppression_reason(email: str | None) -> str | None:
    """Return a machine-readable refusal reason, or None if not suppressed.

    Not suppressed does NOT imply deliverability or authorization to send.
    """
    if not email or not str(email).strip():
        return "no_email"
    address = str(email).strip().casefold()
    if not _EMAIL.fullmatch(address):
        return "invalid_email"
    digest = hashlib.sha256(address.encode("utf-8")).hexdigest()
    if digest in _FAILED_RECIPIENT_HASHES:
        return "delivery_failure_suppressed"
    if address in _csv_env("FLEET_SUPPRESSED_EMAILS"):
        return "operator_suppressed"
    if address.rsplit("@", 1)[-1] in _csv_env("FLEET_SUPPRESSED_DOMAINS"):
        return "operator_suppressed_domain"
    return None
