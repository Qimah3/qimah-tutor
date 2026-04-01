import os
import sys
import hashlib
import hmac
import time
import json
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _sign(body: bytes, secret: str, timestamp: str = None, nonce: str = None):
    """Helper: sign a request body with HMAC-SHA256."""
    ts = timestamp or str(int(time.time()))
    n = nonce or str(uuid.uuid4())
    body_hash = hashlib.sha256(body).hexdigest()
    sig = hmac.new(secret.encode(), (ts + n + body_hash).encode(), hashlib.sha256).hexdigest()
    return sig, ts, n


def test_valid_request():
    from app.auth import verify_request
    body = json.dumps({"type": "quiz"}).encode()
    sig, ts, nonce = _sign(body, "test-secret")
    assert verify_request(sig, ts, nonce, body, "test-secret") is True


def test_expired_timestamp():
    from app.auth import verify_request
    body = b'{"type":"quiz"}'
    sig, ts, nonce = _sign(body, "test-secret", timestamp=str(int(time.time()) - 120))
    assert verify_request(sig, ts, nonce, body, "test-secret", window=60) is False


def test_future_timestamp_rejected():
    """Timestamps more than window seconds in the future are rejected."""
    from app.auth import verify_request
    body = b'{"type":"quiz"}'
    sig, ts, nonce = _sign(body, "test-secret", timestamp=str(int(time.time()) + 120))
    assert verify_request(sig, ts, nonce, body, "test-secret", window=60) is False


def test_wrong_signature():
    from app.auth import verify_request
    assert verify_request("badsig", str(int(time.time())), "nonce1", b'{}', "secret") is False


def test_replay_rejected():
    from app.auth import verify_request, _seen_nonces
    _seen_nonces.clear()
    body = b'{"type":"quiz"}'
    sig, ts, nonce = _sign(body, "secret")
    assert verify_request(sig, ts, nonce, body, "secret") is True
    # Same nonce again = replay
    assert verify_request(sig, ts, nonce, body, "secret") is False


def test_malformed_timestamp_string():
    from app.auth import verify_request
    assert verify_request("sig", "not-a-number", "nonce", b'{}', "secret") is False


def test_empty_timestamp():
    from app.auth import verify_request
    assert verify_request("sig", "", "nonce", b'{}', "secret") is False


def test_different_nonces_not_replayed():
    """Two different nonces for the same body+secret should both succeed."""
    from app.auth import verify_request, _seen_nonces
    _seen_nonces.clear()
    body = b'{"type":"quiz"}'
    sig1, ts1, nonce1 = _sign(body, "secret")
    sig2, ts2, nonce2 = _sign(body, "secret")
    assert nonce1 != nonce2  # sanity
    assert verify_request(sig1, ts1, nonce1, body, "secret") is True
    assert verify_request(sig2, ts2, nonce2, body, "secret") is True
