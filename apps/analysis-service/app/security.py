"""Shared security primitives: input sanitization/validation, password
hashing, and a lightweight in-memory rate limiter.

Rate limiting and account-lockout state are kept in-process (a dict), which is
correct as long as the API runs as a single instance — already a requirement
elsewhere in this app (the daily signal scan assumes one process). If you ever
scale to multiple instances, move this state to Redis or the database.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from collections import defaultdict

from fastapi import HTTPException, Request

# ---------------------------------------------------------------------------
# Password hashing — scrypt (memory-hard, stdlib only). Falls back to
# verifying legacy PBKDF2-SHA256 hashes created before this upgrade, and
# transparently re-hashes them to scrypt on the next successful login.
# ---------------------------------------------------------------------------
_SCRYPT_N = 2**14   # CPU/memory cost
_SCRYPT_R = 8
_SCRYPT_P = 1
_LEGACY_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> tuple[bool, bool]:
    """Returns (is_valid, needs_rehash). needs_rehash is True for any
    legacy-format hash so the caller can upgrade it after a successful login."""
    parts = stored.split("$")
    try:
        if stored.startswith("scrypt$") and len(parts) == 6:
            _, n, r, p, salt_hex, hash_hex = parts
            derived = hashlib.scrypt(
                password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=32
            )
            return hmac.compare_digest(derived, bytes.fromhex(hash_hex)), False

        # legacy format: "<salt_hex>$<hash_hex>", PBKDF2-HMAC-SHA256, fixed iterations
        if len(parts) == 2:
            salt_hex, hash_hex = parts
            derived = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt_hex), _LEGACY_PBKDF2_ITERATIONS
            )
            return hmac.compare_digest(derived, bytes.fromhex(hash_hex)), True
    except (ValueError, IndexError):
        pass
    return False, False


# ---------------------------------------------------------------------------
# Input sanitization / validation. Every field a user can submit is normalized
# and re-checked here, server-side, regardless of what the frontend already
# validated client-side.
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{1,24}$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_NAME_RE = re.compile(r"^[A-Za-zÀ-ɏ' .-]{2,100}$")
_CODE_RE = re.compile(r"^\d{6}$")

# common/weak passwords rejected outright regardless of length/complexity
_WEAK_PASSWORDS = {
    "password", "password1", "12345678", "123456789", "qwertyui",
    "letmein1", "iloveyou", "admin123", "welcome1", "passw0rd",
}


def normalize_email(email: str) -> str:
    email = _CONTROL_CHARS_RE.sub("", email).strip().lower()
    if not email or len(email) > 254 or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="enter a valid email address")
    return email


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")
    if len(password) > 128:
        raise HTTPException(status_code=400, detail="password is too long")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="password must include at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="password must include at least one lowercase letter")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="password must include at least one number")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(status_code=400, detail="password must include at least one special character (e.g. ! @ # $ %)")
    if password.lower() in _WEAK_PASSWORDS:
        raise HTTPException(status_code=400, detail="that password is too common — choose a stronger one")
    return password


def password_must_be_unique_to_user(password: str, email: str, full_name: str | None) -> None:
    """Reject passwords trivially derived from the user's own identity (their
    email's local-part or their name) — a common, easily-guessed pattern."""
    lowered = password.lower()
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 3 and local_part in lowered:
        raise HTTPException(status_code=400, detail="password must not contain your email address")
    if full_name:
        for token in re.split(r"\s+", full_name.lower()):
            if len(token) >= 3 and token in lowered:
                raise HTTPException(status_code=400, detail="password must not contain your name")


def sanitize_full_name(name: str) -> str:
    name = _CONTROL_CHARS_RE.sub("", name).strip()
    name = re.sub(r"\s+", " ", name)
    parts = name.split()
    if (
        not name
        or len(name) < 3
        or len(name) > 100
        or not _NAME_RE.match(name)
        or len(parts) < 2
        or any(len(p) < 1 for p in parts)
    ):
        raise HTTPException(status_code=400, detail="Invalid name — please enter your first and last name.")
    return name


def sanitize_phone(phone: str) -> str:
    phone = _CONTROL_CHARS_RE.sub("", phone).strip()
    # keep a leading + and digits only
    cleaned = re.sub(r"[^\d+]", "", phone)
    digits_only = re.sub(r"\D", "", cleaned)
    if len(digits_only) < 7 or len(digits_only) > 15:
        raise HTTPException(status_code=400, detail="enter a valid phone number (7-15 digits)")
    return cleaned


def validate_code(code: str) -> str:
    code = code.strip()
    if not _CODE_RE.match(code):
        raise HTTPException(status_code=400, detail="enter the 6-digit code")
    return code


def sanitize_token_field(value: str, max_len: int = 200) -> str:
    """Generic cleanup for broker account ids / API tokens etc — strip
    control chars and whitespace, cap length."""
    value = _CONTROL_CHARS_RE.sub("", value).strip()
    if len(value) > max_len:
        raise HTTPException(status_code=400, detail="value is too long")
    return value


# ---------------------------------------------------------------------------
# Rate limiting (sliding window, in-memory) + account lockout helpers.
# ---------------------------------------------------------------------------
_hits: dict[str, list[float]] = defaultdict(list)


def get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    """Raise 429 if `bucket` (e.g. 'login:<ip>') exceeded `limit` hits within
    `window_seconds`. Call once per request attempt, before doing the work."""
    key = f"{bucket}:{get_client_ip(request)}"
    now = time.time()
    window_start = now - window_seconds
    hits = [t for t in _hits[key] if t > window_start]
    if len(hits) >= limit:
        retry_after = int(hits[0] + window_seconds - now) + 1
        raise HTTPException(
            status_code=429,
            detail="too many attempts — please wait before trying again",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
    hits.append(now)
    _hits[key] = hits
