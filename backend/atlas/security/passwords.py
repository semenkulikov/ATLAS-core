"""Argon2id password hashes.

The memory setting is 19 MiB so a login stays inside the process budget.
The parameters are fixed here so every install verifies the same way.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, hash_len=32, salt_len=16)
_DUMMY = HASHER.hash("atlas-timing-pad")


def hash_password(password: str) -> str:
    """Return an Argon2id hash. The password itself is not retained."""
    return HASHER.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check a password. A missing account still runs a hash compare."""
    try:
        return HASHER.verify(password_hash or _DUMMY, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
