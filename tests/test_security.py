import hashlib
import hmac

from src.main import verify_permit_signature


def make_signature(payload: bytes, timestamp: int, secret: str) -> str:
    message = str(timestamp).encode("ascii") + b"." + payload
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return "sha256=" + digest


def test_valid_permit_signature_is_accepted():
    payload = b'{"permit_id":"P-1"}'
    timestamp = 1_800_000_000
    signature = make_signature(payload, timestamp, "test-secret-with-more-than-32-bytes-long")
    assert verify_permit_signature(
        payload, str(timestamp), signature, "test-secret-with-more-than-32-bytes-long", now=timestamp
    )


def test_tampered_payload_is_rejected():
    timestamp = 1_800_000_000
    signature = make_signature(b'{"permit_id":"P-1"}', timestamp, "test-secret-with-more-than-32-bytes-long")
    assert not verify_permit_signature(
        b'{"permit_id":"P-2"}',
        str(timestamp),
        signature,
        "test-secret-with-more-than-32-bytes-long",
        now=timestamp,
    )


def test_expired_signature_is_rejected():
    timestamp = 1_800_000_000
    signature = make_signature(b"{}", timestamp, "test-secret-with-more-than-32-bytes-long")
    assert not verify_permit_signature(
        b"{}", str(timestamp), signature, "test-secret-with-more-than-32-bytes-long", now=timestamp + 301
    )


def test_missing_or_malformed_signature_is_rejected():
    assert not verify_permit_signature(b"{}", "", "sha256=bad", "secret")
    assert not verify_permit_signature(b"{}", "not-a-time", "sha256=bad", "secret")
    assert not verify_permit_signature(b"{}", "1800000000", "sha256=bad", "secret")
