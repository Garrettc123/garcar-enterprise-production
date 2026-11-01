"""Run a non-destructive Vault and S3 production-readiness preflight.

The script prints check results only. It never prints secret values, creates cloud
resources, changes bucket retention, writes ledger objects, or moves money.
"""
from __future__ import annotations

import json
import sys

from src.main import _s3_client, load_runtime_config, verify_worm_configuration


def main() -> int:
    try:
        config = load_runtime_config()
    except Exception as exc:
        print(json.dumps({
            "ready": False,
            "failed_check": "vault_runtime_configuration",
            "error_type": type(exc).__name__,
        }, sort_keys=True))
        return 2

    try:
        retention = verify_worm_configuration(
            _s3_client(),
            config["S3_LEDGER_BUCKET"],
        )
    except Exception as exc:
        print(json.dumps({
            "ready": False,
            "failed_check": "s3_bucket_security",
            "error_type": type(exc).__name__,
        }, sort_keys=True))
        return 2

    print(json.dumps({
        "ready": True,
        "checks": {
            "vault_approle_and_secret_formats": True,
            "object_lock_compliance": retention["mode"] == "COMPLIANCE",
            "bucket_versioning": True,
            "public_access_block": retention["public_access_blocked"],
            "server_side_encryption": retention["encryption"],
        },
        "retention": {
            "mode": retention["mode"],
            "days": retention["days"],
            "years": retention["years"],
        },
        "actions_performed": [],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
