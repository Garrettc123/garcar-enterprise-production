"""Regression tests for head-linked S3 ledger verification."""
from __future__ import annotations

import hashlib
import io
import json
from typing import Any

from scripts import verify_chain


def make_event(event_id: str, sequence: int, previous_hash: str) -> tuple[str, str, dict[str, Any]]:
    record = {
        "event_id": event_id,
        "event_type": "TEST_EVENT",
        "chain": {"sequence": sequence, "previous_hash": previous_hash},
    }
    canonical = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    stored = {**record, "sha256": digest}
    key = f"evidence/chain/events/{sequence:020d}-{event_id}.json"
    response = {
        "Body": io.BytesIO(json.dumps(stored).encode("utf-8")),
        "Metadata": {"sha256": digest},
        "ObjectLockMode": "COMPLIANCE",
        "ObjectLockRetainUntilDate": "2027-10-31T00:00:00Z",
    }
    return key, digest, response


class FakePaginator:
    def __init__(self, keys: list[str]):
        self.keys = keys

    def paginate(self, **_kwargs):
        return [{"Contents": [{"Key": key} for key in self.keys]}]


class FakeS3:
    def __init__(self, objects: dict[str, dict[str, Any]]):
        self.objects = objects

    def get_paginator(self, _name: str):
        event_keys = sorted(
            key for key in self.objects if key.startswith("evidence/chain/events/")
        )
        return FakePaginator(event_keys)

    def get_object(self, Bucket: str, Key: str):
        del Bucket
        source = self.objects[Key]
        return {**source, "Body": io.BytesIO(source["Body"].getvalue())}


def make_head(sequence: int, event_hash: str) -> dict[str, Any]:
    return {
        "Body": io.BytesIO(
            json.dumps({"sequence": sequence, "event_hash": event_hash}).encode("utf-8")
        ),
        "ObjectLockMode": "COMPLIANCE",
        "ObjectLockRetainUntilDate": "2027-10-31T00:00:00Z",
    }


def patch_s3(monkeypatch, fake_s3: FakeS3) -> None:
    monkeypatch.setattr(verify_chain.boto3, "client", lambda *_args, **_kwargs: fake_s3)


def test_verifies_committed_chain_by_head_hash(monkeypatch):
    key1, hash1, event1 = make_event("evt-1", 1, verify_chain.ZERO_HASH)
    key2, hash2, event2 = make_event("evt-2", 2, hash1)
    objects = {
        key1: event1,
        key2: event2,
        "evidence/chain/head.json": make_head(2, hash2),
    }
    patch_s3(monkeypatch, FakeS3(objects))

    valid, detail = verify_chain.verify("ledger", "us-east-1")

    assert valid is True
    assert detail == "verified 2 committed events; no orphan objects"


def test_unlinked_concurrent_write_is_flagged_as_orphan(monkeypatch):
    orphan_key, _orphan_hash, orphan = make_event(
        "evt-loser", 1, verify_chain.ZERO_HASH
    )
    winner_key, winner_hash, winner = make_event(
        "evt-winner", 1, verify_chain.ZERO_HASH
    )
    next_key, next_hash, next_event = make_event("evt-2", 2, winner_hash)
    objects = {
        orphan_key: orphan,
        winner_key: winner,
        next_key: next_event,
        "evidence/chain/head.json": make_head(2, next_hash),
    }
    patch_s3(monkeypatch, FakeS3(objects))

    valid, detail = verify_chain.verify("ledger", "us-east-1")

    assert valid is False
    assert "committed chain is valid for 2 events" in detail
    assert "1 unlinked immutable event object" in detail


def test_tampered_event_fails_integrity_check(monkeypatch):
    key, digest, event = make_event("evt-1", 1, verify_chain.ZERO_HASH)
    tampered = json.loads(event["Body"].getvalue())
    tampered["event_type"] = "ALTERED"
    event["Body"] = io.BytesIO(json.dumps(tampered).encode("utf-8"))
    objects = {
        key: event,
        "evidence/chain/head.json": make_head(1, digest),
    }
    patch_s3(monkeypatch, FakeS3(objects))

    valid, detail = verify_chain.verify("ledger", "us-east-1")

    assert valid is False
    assert "content hash mismatch" in detail
