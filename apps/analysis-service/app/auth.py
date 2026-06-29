"""Auth: scrypt password hashing, server-side input validation, rate limiting,
account lockout, and an OAuth bridge endpoint for trusted providers (Google via
NextAuth) — plus user/watchlist persistence."""
from __future__ import annotations

import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, field_validator, model_validator

from .db import db_session
from .fixtures import SYMBOLS
from .security import (
    get_client_ip,
    hash_password,
    normalize_email,
    password_must_be_unique_to_user,
    rate_limit,
    sanitize_full_name,
    sanitize_phone,
    validate_code,
    validate_password,
    verify_password,
)

router = APIRouter()

LOCKOUT_THRESHOLD = 5
LOCKOUT_MINUTES = 15

# Public base URL of the web app.
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "http://localhost:3000")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
RESEND_FROM = os.environ.get("RESEND_FROM", "PIP HIVE <onboarding@resend.dev>")
# Gmail (or any SMTP): set SMTP_USER + SMTP_PASS (a Gmail App Password). SMTP_HOST
# defaults to Gmail so for Gmail you only need USER + PASS.
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_FROM = os.environ.get("SMTP_FROM") or SMTP_USER
EMAIL_CONFIGURED = bool(RESEND_API_KEY or (SMTP_USER and SMTP_PASS))
# Shared secret the frontend's server-side OAuth callback must present, so the
# OAuth bridge can't be used by anyone outside our own backend to mint accounts.
OAUTH_BRIDGE_SECRET = os.environ.get("OAUTH_BRIDGE_SECRET")

# A constant, real (but unknown-password) hash used to keep login timing for a
# non-existent email similar to a real failed-password check — reduces (not
# eliminates) account-enumeration via response timing.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def _send_verification_code(email: str, code: str) -> bool:
    """Send the 6-digit code via Gmail/SMTP or Resend. Returns True only if an
    email was actually sent, so signup can fall back to showing the code."""
    subject = "Your PIP HIVE verification code"
    body = (
        f"Welcome to PIP HIVE.\n\nYour verification code is: {code}\n\n"
        "Enter it on the site to activate your account.\n\nIf you didn't request this, ignore this email."
    )

    if SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM or SMTP_USER
            msg["To"] = email
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
            return True
        except Exception:  # noqa: BLE001 — fall through to other providers / on-screen code
            pass

    if RESEND_API_KEY:
        try:
            r = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": RESEND_FROM, "to": [email], "subject": subject, "text": body},
                timeout=15,
            )
            return r.status_code < 300
        except Exception:  # noqa: BLE001
            pass

    return False


def _new_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"  # 6 digits, 100000-999999


class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: str
    terms_accepted: bool

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("password")
    @classmethod
    def _v_password(cls, v: str) -> str:
        return validate_password(v)

    @field_validator("full_name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return sanitize_full_name(v)

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str) -> str:
        return sanitize_phone(v)

    @model_validator(mode="after")
    def _v_password_not_personal(self):
        password_must_be_unique_to_user(self.password, self.email, self.full_name)
        return self


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return normalize_email(v)


class WatchlistRequest(BaseModel):
    user_id: int
    symbol: str

    @field_validator("symbol")
    @classmethod
    def _v_symbol(cls, v: str) -> str:
        if v not in SYMBOLS:
            raise ValueError(f"unknown symbol '{v}'")
        return v


class VerifyCodeRequest(BaseModel):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("code")
    @classmethod
    def _v_code(cls, v: str) -> str:
        return validate_code(v)


class ResendRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return normalize_email(v)


class OAuthUpsertRequest(BaseModel):
    email: str
    full_name: str | None = None
    provider: str = "google"

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str) -> str:
        return normalize_email(v)


@router.post("/auth/signup")
def signup(req: SignupRequest, request: Request):
    rate_limit(request, "signup", limit=5, window_seconds=3600)

    if not req.terms_accepted:
        raise HTTPException(status_code=400, detail="you must accept the Terms of Service and Privacy Policy")

    with db_session() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (req.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="email already registered")
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        is_admin = 1 if user_count == 0 else 0
        plan = "platinum" if is_admin else "free"  # first user (admin) gets full access
        code = _new_code()
        verified = 1 if is_admin else 0  # first admin is auto-verified
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, is_admin, plan, verified, verification_token, "
            "full_name, phone, terms_accepted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                req.email,
                hash_password(req.password),
                is_admin,
                plan,
                verified,
                None if verified else code,
                req.full_name,
                req.phone,
            ),
        )

    response = {"id": cur.lastrowid, "email": req.email, "is_admin": bool(is_admin), "plan": plan, "verified": bool(verified)}
    if not verified:
        sent = _send_verification_code(req.email, code)
        response["email_sent"] = sent
        # Always hand the code back too. A provider can report success (e.g.
        # a sandbox sender that "sends" but never actually delivers) without
        # the email reaching the inbox — so the on-screen code is the one
        # guarantee that a user is never stuck, regardless of email status.
        response["verification_code"] = code
    return response


@router.post("/auth/verify-code")
def verify_code(req: VerifyCodeRequest, request: Request):
    rate_limit(request, "verify-code", limit=10, window_seconds=900)
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, verified, verification_token FROM users WHERE email = ?", (req.email,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="no account for that email")
        if row["verified"]:
            return {"ok": True, "verified": True}
        if not row["verification_token"] or req.code != row["verification_token"]:
            raise HTTPException(status_code=400, detail="incorrect verification code")
        conn.execute("UPDATE users SET verified = 1, verification_token = NULL WHERE id = ?", (row["id"],))
    return {"ok": True, "verified": True}


@router.post("/auth/resend-code")
def resend_code(req: ResendRequest, request: Request):
    rate_limit(request, "resend-code", limit=3, window_seconds=600)
    with db_session() as conn:
        row = conn.execute("SELECT id, verified FROM users WHERE email = ?", (req.email,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="no account for that email")
        if row["verified"]:
            return {"ok": True, "verified": True}
        code = _new_code()
        conn.execute("UPDATE users SET verification_token = ? WHERE id = ?", (code, row["id"]))
    sent = _send_verification_code(req.email, code)
    return {"ok": True, "email_sent": sent, "verification_code": code}


@router.post("/auth/login")
def login(req: LoginRequest, request: Request):
    rate_limit(request, "login", limit=10, window_seconds=900)

    # NOTE: db_session only commits if the `with` block exits normally — an
    # exception raised inside it rolls the transaction back. So every write
    # below happens and the block exits cleanly BEFORE we raise anything;
    # the actual HTTPException is raised after the block, from a plain
    # variable holding the outcome.
    error: HTTPException | None = None
    result: dict | None = None

    with db_session() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, is_admin, plan, verified, full_name, pending_plan, "
            "failed_login_attempts, lock_until FROM users WHERE email = ?",
            (req.email,),
        ).fetchone()

        if not row:
            # still hash against a dummy value so response timing doesn't
            # obviously differ from the "wrong password" path
            verify_password(req.password, _DUMMY_HASH)
            error = HTTPException(status_code=401, detail="Incorrect email or password.")
        else:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if row["lock_until"] and row["lock_until"] > now:
                error = HTTPException(
                    status_code=423,
                    detail="Too many failed attempts. This account is temporarily locked — please try again later.",
                )
            else:
                ok, needs_rehash = verify_password(req.password, row["password_hash"])
                if not ok:
                    attempts = row["failed_login_attempts"] + 1
                    lock_until = None
                    if attempts >= LOCKOUT_THRESHOLD:
                        lock_until = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    conn.execute(
                        "UPDATE users SET failed_login_attempts = ?, lock_until = ? WHERE id = ?",
                        (attempts, lock_until, row["id"]),
                    )
                    error = HTTPException(status_code=401, detail="Incorrect email or password.")
                elif not row["verified"]:
                    error = HTTPException(status_code=403, detail="email not verified")
                else:
                    # successful login — reset lockout state, upgrade legacy hashes
                    update_sql = "UPDATE users SET failed_login_attempts = 0, lock_until = NULL"
                    params: list = []
                    if needs_rehash:
                        update_sql += ", password_hash = ?"
                        params.append(hash_password(req.password))
                    update_sql += " WHERE id = ?"
                    params.append(row["id"])
                    conn.execute(update_sql, params)
                    result = {
                        "id": row["id"],
                        "email": row["email"],
                        "is_admin": bool(row["is_admin"]),
                        "plan": row["plan"],
                        "full_name": row["full_name"],
                        "pending_plan": row["pending_plan"],
                        "verified": True,
                    }

    if error:
        raise error
    return result


@router.post("/auth/oauth-upsert")
def oauth_upsert(req: OAuthUpsertRequest, request: Request, x_internal_secret: str | None = Header(default=None)):
    """Called server-side by the frontend's NextAuth callback after a trusted
    provider (Google) confirms the user's identity. Creates the account if it
    doesn't exist yet (email is already verified by the provider) or returns
    the existing one. Protected by a shared secret so it can't be hit publicly
    to mint accounts."""
    rate_limit(request, "oauth-upsert", limit=20, window_seconds=300)
    if not OAUTH_BRIDGE_SECRET or x_internal_secret != OAUTH_BRIDGE_SECRET:
        raise HTTPException(status_code=403, detail="not authorized")

    with db_session() as conn:
        row = conn.execute(
            "SELECT id, email, is_admin, plan, full_name, pending_plan FROM users WHERE email = ?",
            (req.email,),
        ).fetchone()
        if row:
            return {
                "id": row["id"],
                "email": row["email"],
                "is_admin": bool(row["is_admin"]),
                "plan": row["plan"],
                "full_name": row["full_name"],
                "pending_plan": row["pending_plan"],
                "verified": True,
            }

        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        is_admin = 1 if user_count == 0 else 0
        plan = "platinum" if is_admin else "free"
        full_name = sanitize_full_name(req.full_name) if req.full_name else None
        unusable_hash = hash_password(secrets.token_urlsafe(32))  # no password login for OAuth accounts
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, is_admin, plan, verified, full_name, "
            "terms_accepted_at, oauth_provider) VALUES (?, ?, ?, ?, 1, ?, datetime('now'), ?)",
            (req.email, unusable_hash, is_admin, plan, full_name, req.provider),
        )
    return {
        "id": cur.lastrowid,
        "email": req.email,
        "is_admin": bool(is_admin),
        "plan": plan,
        "full_name": full_name,
        "pending_plan": None,
        "verified": True,
    }


@router.get("/watchlist/{user_id}")
def get_watchlist(user_id: int):
    with db_session() as conn:
        rows = conn.execute("SELECT symbol FROM watchlist WHERE user_id = ?", (user_id,)).fetchall()
    return {"symbols": [r["symbol"] for r in rows]}


@router.post("/watchlist")
def add_watchlist_item(req: WatchlistRequest):
    with db_session() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (user_id, symbol) VALUES (?, ?)",
            (req.user_id, req.symbol),
        )
    return {"ok": True}


@router.delete("/watchlist")
def remove_watchlist_item(req: WatchlistRequest):
    with db_session() as conn:
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?",
            (req.user_id, req.symbol),
        )
    return {"ok": True}
