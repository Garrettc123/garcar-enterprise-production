"""Sign a JSON owner-approval document with the offline Ed25519 private key."""
from __future__ import annotations

import argparse
import base64
import getpass
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from src.governance import OwnerApproval, canonical_approval


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-json", required=True)
    parser.add_argument("--private-key", required=True)
    args = parser.parse_args()
    approval = OwnerApproval.model_validate_json(
        Path(args.approval_json).read_text(encoding="utf-8")
    )
    passphrase = getpass.getpass("Private-key passphrase: ")
    private = serialization.load_pem_private_key(
        Path(args.private_key).read_bytes(),
        password=passphrase.encode(),
    )
    signature = private.sign(canonical_approval(approval))
    print(base64.b64encode(signature).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
