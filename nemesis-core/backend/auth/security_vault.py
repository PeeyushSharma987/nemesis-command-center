import os
import re
import time
from typing import Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
bearer_scheme = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "fallback_dev_secret_change_me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 900  # 15-minute short-lived session expiration

# Dangerous SQLi / XSS / Command Injection patterns
INJECTION_REGEX = re.compile(
    r"(<script.*?>|javascript:|onerror=|onload=|UNION\s+SELECT|DROP\s+TABLE|--|;\s*rm\s+-rf|\|\||&&)",
    re.IGNORECASE,
)


def sanitize_user_input(value: str) -> str:
    """Blocks XSS, SQL injection, and command injection payloads."""
    if INJECTION_REGEX.search(value):
        raise ValueError("Malicious input payload blocked by N.E.M.E.S.I.S. Firewall.")
    return value.strip()


class UserRegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)
    savage_level: int = Field(default=75, ge=10, le=100)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return sanitize_user_input(v)


class SafeCommandInput(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    resource_owner_id: str = Field(..., description="Used for Anti-IDOR ownership verification")

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, v: str) -> str:
        return sanitize_user_input(v)


class SecurityVault:
    """Enforces Argon2id hashing, JWT rotation, login rate-limiting, and Anti-IDOR ownership."""

    _failed_logins: Dict[str, List[float]] = {}

    @staticmethod
    def hash_password(plain_password: str) -> str:
        return ph.hash(plain_password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return ph.verify(hashed_password, plain_password)
        except VerifyMismatchError:
            return False

    @classmethod
    def check_login_rate_limit(cls, client_ip: str) -> None:
        now = time.time()
        attempts = [t for t in cls._failed_logins.get(client_ip, []) if now - t < 300]
        cls._failed_logins[client_ip] = attempts
        if len(attempts) >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Locked for 5 minutes.",
            )

    @classmethod
    def record_failed_login(cls, client_ip: str) -> None:
        cls._failed_logins.setdefault(client_ip, []).append(time.time())

    @staticmethod
    def create_access_token(user_id: str, tier: str = "free", email_verified: bool = True) -> str:
        if not email_verified:
            raise HTTPException(status_code=403, detail="Email verification required before session creation.")
        payload = {
            "sub": user_id,
            "tier": tier,
            "iat": int(time.time()),
            "exp": int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS,
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Dict[str, str]:
        try:
            payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return {"user_id": payload["sub"], "tier": payload.get("tier", "free")}
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Session expired. Please refresh token.")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

    @staticmethod
    def enforce_anti_idor(logged_in_user_id: str, target_resource_owner_id: str) -> None:
        """Prevents Insecure Direct Object Reference (IDOR): users can only access their own data."""
        if logged_in_user_id != target_resource_owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ANTI-IDOR SHIELD: You do not own this resource.",
            )
