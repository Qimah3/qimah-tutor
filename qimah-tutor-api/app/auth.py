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
    - nonce is present and has not been seen before (within the cache window)
    - signature matches the expected value
    """
    # 1. Validate and parse timestamp
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False
    if abs(time.time() - ts) > window:
        return False

    # 2. Reject missing nonce values so integrations cannot silently disable
    # replay protection by signing with an empty nonce.
    if not nonce:
        return False

    # 3. Prune expired nonces (older than window)
    cutoff = time.time() - window
    expired = [k for k, v in _seen_nonces.items() if v < cutoff]
    for k in expired:
        del _seen_nonces[k]

    # 4. Verify signature before touching the nonce cache so malformed requests
    # cannot burn valid nonces or evict real entries from the replay window.
    body_hash = hashlib.sha256(body).hexdigest()
    expected = hmac.new(
        secret.encode(),
        (timestamp + nonce + body_hash).encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False

    # 5. Reject replayed nonces after authentication succeeds.
    if nonce in _seen_nonces:
        return False

    # 6. Record the authenticated nonce.
    _seen_nonces[nonce] = ts
    while len(_seen_nonces) > _MAX_NONCES:
        _seen_nonces.popitem(last=False)

    return True
