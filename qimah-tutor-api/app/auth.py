import hashlib
import hmac
import time
from collections import OrderedDict

# Bounded nonce cache — prevents replay within the timestamp window.
# In-memory only: resets on process restart (acceptable for pilot).
_seen_nonces: OrderedDict = OrderedDict()
_MAX_NONCES = 10000


def verify_request(
    signature: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    secret: str,
    window: int = 60,
) -> bool:
    """Verify a timestamp-bounded HMAC-SHA256 request signature.

    Signature = HMAC-SHA256(timestamp + nonce + sha256(body))

    Returns True only if:
    - timestamp is an integer within `window` seconds of now
    - nonce has not been seen before (within the cache window)
    - signature matches the expected value
    """
    # 1. Validate and parse timestamp
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    if abs(time.time() - ts) > window:
        return False

    # 2. Prune expired nonces (older than window)
    cutoff = time.time() - window
    expired = [k for k, v in _seen_nonces.items() if v < cutoff]
    for k in expired:
        del _seen_nonces[k]

    # 3. Reject replayed nonces
    if nonce in _seen_nonces:
        return False

    # 4. Record nonce (do this before signature check so replay is still blocked
    #    even if someone submits the same nonce with a bad signature)
    _seen_nonces[nonce] = ts
    while len(_seen_nonces) > _MAX_NONCES:
        _seen_nonces.popitem(last=False)

    # 5. Verify signature
    body_hash = hashlib.sha256(body).hexdigest()
    expected = hmac.new(
        secret.encode(),
        (timestamp + nonce + body_hash).encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
