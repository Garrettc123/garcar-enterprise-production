"""Generate an owner Ed25519 keypair locally; never commit the private key."""
from __future__ import annotations

import argparse
import base64
import getpass
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def write_new_private_file(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-key-out", required=True)
    parser.add_argument("--public-key-out", required=True)
    args = parser.parse_args()
    private_path = Path(args.private_key_out)
    public_path = Path(args.public_key_out)
    if private_path.resolve() == public_path.resolve():
        parser.error("private and public key paths must differ")
    passphrase = getpass.getpass("Private-key passphrase (min 12 characters): ")
    if len(passphrase) < 12:
        parser.error("passphrase must be at least 12 characters")
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase.encode()),
    )
    public_raw = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    public_b64 = base64.b64encode(public_raw).decode("ascii")
    write_new_private_file(private_path, private_pem)
    try:
        public_path.write_text(public_b64 + "\n", encoding="utf-8")
    except Exception:
        private_path.unlink(missing_ok=True)
        raise
    os.chmod(public_path, 0o644)
    print(f"Private key saved locally: {private_path}")
    print("Public key (store in Vault as OWNER_APPROVAL_PUBLIC_KEY):")
    print(public_b64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
