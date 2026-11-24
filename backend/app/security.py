import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

# 64 MiB per operation; global throttling constrains load on the office VM.
hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))

def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Password must be 12–128 characters")
    return hasher.hash(password)

def verify_password(password: str, encoded: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
