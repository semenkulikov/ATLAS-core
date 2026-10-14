"""Random tokens stored only as SHA-256 hashes."""

from __future__ import annotations

import hashlib
import secrets

import pyotp


def new_token() -> str:
    """Return a URL-safe secret. The caller shows it once and stores the hash."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a bearer or session token. The raw value never goes into the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_totp_secret() -> str:
    """Return a base32 TOTP secret for an authenticator application."""
    return str(pyotp.random_base32())


def provisioning_uri(secret: str, username: str) -> str:
    """Build the otpauth URI the owner scans once while enrolling."""
    return str(pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="ATLAS"))


def verify_totp(secret: str, code: str) -> bool:
    """Accept the current code and one step either side, for clock skew."""
    if not code.isdigit():
        return False
    return bool(pyotp.TOTP(secret).verify(code, valid_window=1))
