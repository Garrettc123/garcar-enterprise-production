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
