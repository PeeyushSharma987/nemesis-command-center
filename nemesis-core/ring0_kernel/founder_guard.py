import hmac
import os
from fastapi import Header, HTTPException, status


def verify_founder_god_key(x_founder_key: str = Header(..., alias="X-Founder-God-Key")) -> bool:
    """Ring-0 immutable check: Only the Founder can trigger self-mutation or admin overrides."""
    expected_key = os.getenv("FOUNDER_GOD_KEY", "")
    if not expected_key or not hmac.compare_digest(x_founder_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="N.E.M.E.S.I.S. RING-0 LOCK: Unauthorized access attempt logged.",
        )
    return True
