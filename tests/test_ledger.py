import hashlib
import json
from datetime import datetime, timedelta, timezone
from src import ledger

class FakeS3:
    def __init__(self):
        self.args = None
    def put_object(self, **kwargs):
        self.args = kwargs
        return {"VersionId": "v1"}

def test_seal_record_writes_compliance_retention(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(ledger.boto3, "client", lambda *a, **k: fake)
    record = {"b": 2, "a": 1}
    result = ledger.seal_record(record, "ledger-bucket", "us-east-1", 30)
    expected = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert result["sha256"] == expected
    assert result["version_id"] == "v1"
    assert fake.args["ObjectLockMode"] == "COMPLIANCE"
    assert fake.args["IfNoneMatch"] == "*"
    assert fake.args["ObjectLockRetainUntilDate"] > datetime.now(timezone.utc) + timedelta(days=29)

def test_seal_record_fails_without_bucket():
    import pytest
    with pytest.raises(ledger.LedgerError):
        ledger.seal_record({"x": 1}, "", "us-east-1", 30)


def test_seal_record_retries_conditional_conflict(monkeypatch):
    from botocore.exceptions import ClientError

    class ConflictThenSuccess(FakeS3):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def put_object(self, **kwargs):
            self.calls += 1
            self.args = kwargs
            if self.calls == 1:
                raise ClientError(
                    {"Error": {"Code": "ConditionalRequestConflict"},
                     "ResponseMetadata": {"HTTPStatusCode": 409}},
                    "PutObject",
                )
            return {"VersionId": "v2"}

    fake = ConflictThenSuccess()
    monkeypatch.setattr(ledger.boto3, "client", lambda *a, **k: fake)
    monkeypatch.setattr(ledger.time, "sleep", lambda _: None)
    result = ledger.seal_record({"id": "conflict"}, "ledger-bucket", "us-east-1", 30)
    assert result["result"] == "sealed"
    assert fake.calls == 2
    assert fake.args["ChecksumAlgorithm"] == "SHA256"


def test_seal_record_duplicate_returns_existing_version(monkeypatch):
    from botocore.exceptions import ClientError

    class ExistingObject(FakeS3):
        def put_object(self, **kwargs):
            self.args = kwargs
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"},
                 "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )

        def head_object(self, **kwargs):
            return {"VersionId": "existing-v1", "Metadata": self.args["Metadata"]}

    fake = ExistingObject()
    monkeypatch.setattr(ledger.boto3, "client", lambda *a, **k: fake)
    result = ledger.seal_record({"id": "duplicate"}, "ledger-bucket", "us-east-1", 30)
    assert result["result"] == "already_sealed"
    assert result["version_id"] == "existing-v1"



def test_seal_record_rejects_existing_object_with_wrong_metadata(monkeypatch):
    from botocore.exceptions import ClientError
    import pytest

    class WrongObject(FakeS3):
        def put_object(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed"},
                 "ResponseMetadata": {"HTTPStatusCode": 412}},
                "PutObject",
            )

        def head_object(self, **kwargs):
            return {
                "VersionId": "different-v1",
                "Metadata": {
                    "garcar-record-sha256": "wrong",
                    "garcar-envelope-sha256": "wrong",
                },
            }

    fake = WrongObject()
    monkeypatch.setattr(ledger.boto3, "client", lambda *a, **k: fake)
    with pytest.raises(ledger.LedgerError, match="metadata does not match"):
        ledger.seal_record({"id": "collision"}, "ledger-bucket", "us-east-1", 30)
