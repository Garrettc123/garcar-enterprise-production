"""Regression tests for chain-head integrity, receipts, and orphan detection."""
from __future__ import annotations

import hashlib
import io
import json
from typing import Any

from scripts import verify_chain


def canonical_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def locked_json(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "Body": io.BytesIO(json.dumps(value).encode("utf-8")),
        "ObjectLockMode": "COMPLIANCE",
        "ObjectLockRetainUntilDate": "2027-10-31T00:00:00Z",
    }


def make_event(
    event_id: str, sequence: int, previous_hash: str
) -> tuple[str, str, dict[str, Any], str]:
    payload = {"event_id": event_id, "event_type": "TEST_EVENT"}
    payload_hash = canonical_hash(payload)
    record = {
        **payload,
        "chain": {"sequence": sequence, "previous_hash": previous_hash},
    }
    digest = canonical_hash(record)
    stored = {**record, "sha256": digest}
    key = f"evidence/chain/events/{sequence:020d}-{event_id}.json"
    response = {
        **locked_json(stored),
        "Metadata": {"sha256": digest},
    }
    return key, digest, response, payload_hash


def add_idempotency_objects(
    objects: dict[str, dict[str, Any]],
    event_id: str,
    payload_hash: str,
    digest: str,
    sequence: int,
) -> None:
    objects[f"evidence/chain/idempotency/{event_id}.json"] = locked_json({
        "event_id": event_id,
        "payload_sha256": payload_hash,
        "state": "RESERVED",
    })
    objects[f"evidence/chain/receipts/{event_id}.json"] = locked_json({
        "event_id": event_id,
        "payload_sha256": payload_hash,
        "event_hash": digest,
        "sequence": sequence,
        "state": "COMMITTED",
    })


class FakePaginator:
    def __init__(self, keys: list[str]):
        self.keys = keys

    def paginate(self, **_kwargs):
        return [{"Contents": [{"Key": key} for key in self.keys]}]


class FakeS3:
    def __init__(self, objects: dict[str, dict[str, Any]]):
        self.objects = objects

    def get_paginator(self, _name: str):
        return FakePaginator([])

    def get_object(self, Bucket: str, Key: str):
        del Bucket
        source = self.objects[Key]
        return {
            **source,
            "Body": io.BytesIO(source["Body"].getvalue()),
        }

    def list_objects_v2(self, **_kwargs):
        raise AssertionError("Verifier should use paginated listing")


class PrefixPaginator(FakePaginator):
    def __init__(self, objects: dict[str, dict[str, Any]], prefix: str):
        self.objects = objects
        self.prefix = prefix

    def paginate(self, **_kwargs):
        keys = sorted(
            key for key in self.objects if key.startswith(self.prefix)
        )
        return [{"Contents": [{"Key": key} for key in keys]}]


def make_s3(objects: dict[str, dict[str, Any]]) -> FakeS3:
    class PrefixAwareFakeS3(FakeS3):
        def get_paginator(self, _name: str):
            # Prefix is supplied when paginate() is called.
            return self

        def paginate(self, Bucket: str, Prefix: str):
            del Bucket
            keys = sorted(key for key in self.objects if key.startswith(Prefix))
            return [{"Contents": [{"Key": key} for key in keys]}]

    return PrefixAwareFakeS3(objects)


def make_head(sequence: int, event_hash: str) -> dict[str, Any]:
    return locked_json({"sequence": sequence, "event_hash": event_hash})


def patch_s3(monkeypatch, fake_s3: FakeS3) -> None:
    monkeypatch.setattr(verify_chain.boto3, "client", lambda *_args, **_kwargs: fake_s3)


def test_verifies_committed_chain_receipts_and_retention(monkeypatch):
    key1, hash1, event1, payload1 = make_event("evt-1", 1, verify_chain.ZERO_HASH)
    key2, hash2, event2, payload2 = make_event("evt-2", 2, hash1)
    objects = {
        key1: event1,
        key2: event2,
        "evidence/chain/head.json": make_head(2, hash2),
    }
    add_idempotency_objects(objects, "evt-1", payload1, hash1, 1)
    add_idempotency_objects(objects, "evt-2", payload2, hash2, 2)
    patch_s3(monkeypatch, make_s3(objects))

    valid, detail = verify_chain.verify("ledger", "us-east-1")

    assert valid is True
    assert detail == "verified 2 committed events, receipts, and retention; no orphans"


def test_unlinked_concurrent_write_is_flagged_as_orphan(monkeypatch):
    orphan_key, _orphan_hash, orphan, orphan_payload = make_event(
        "evt-loser", 1, verify_chain.ZERO_HASH
    )
    winner_key, winner_hash, winner, winner_payload = make_event(
        "evt-winner", 1, verify_chain.ZERO_HASH
    )
    next_key, next_hash, next_event, next_payload = make_event(
        "evt-2", 2, winner_hash
    )
    objects = {
        orphan_key: orphan,
        winner_key: winner,
        next_key: next_event,
        "evidence/chain/head.json": make_head(2, next_hash),
    }
    # The losing writer has a reservation and immutable event, but no receipt:
    # the head compare-and-swap failed, leaving an unlinked orphan.
    objects["evidence/chain/idempotency/evt-loser.json"] = locked_json({
        "event_id": "evt-loser",
        "payload_sha256": orphan_payload,
        "state": "RESERVED",
    })
    add_idempotency_objects(objects, "evt-winner", winner_payload, winner_hash, 1)
    add_idempotency_objects(objects, "evt-2", next_payload, next_hash, 2)
    patch_s3(monkeypatch, make_s3(objects))

    valid, detail = verify_chain.verify("ledger", "us-east-1")

    assert valid is False
    assert "committed chain is valid for 2 events" in detail
    assert "1 unlinked immutable event object" in detail


def test_missing_completion_receipt_fails_verification(monkeypatch):
    key, digest, event, payload_hash = make_event("evt-1", 1, verify_chain.ZERO_HASH)
    objects = {
        key: event,
        "evidence/chain/head.json": make_head(1, digest),
        "evidence/chain/idempotency/evt-1.json": locked_json({
            "event_id": "evt-1",
            "payload_sha256": payload_hash,
            "state": "RESERVED",
        }),
    }
    patch_s3(monkeypatch, make_s3(objects))

    valid, detail = verify_chain.verify("ledger", "us-east-1")

    assert valid is False
    assert detail == "completion receipts do not match committed ledger events"


def test_tampered_event_fails_integrity_check(monkeypatch):
    key, digest, event, payload_hash = make_event("evt-1", 1, verify_chain.ZERO_HASH)
    tampered = json.loads(event["Body"].getvalue())
    tampered["event_type"] = "ALTERED"
    event["Body"] = io.BytesIO(json.dumps(tampered).encode("utf-8"))
    objects = {
        key: event,
        "evidence/chain/head.json": make_head(1, digest),
    }
    add_idempotency_objects(objects, "evt-1", payload_hash, digest, 1)
    patch_s3(monkeypatch, make_s3(objects))

    valid, detail = verify_chain.verify("ledger", "us-east-1")

    assert valid is False
    assert "content hash mismatch" in detail
