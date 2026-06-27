"""Minimal auth: PBKDF2 password hashing (stdlib only, no extra deps) +
user/watchlist persistence in the existing SQLite db."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import smtplib
from email.mime.text import MIMEText

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .db import db_session

router = APIRouter()

_ITERATIONS = 200_000

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
# Email is "configured" if Resend OR Gmail/SMTP credentials are present.
EMAIL_CONFIGURED = bool(RESEND_API_KEY or (SMTP_USER and SMTP_PASS))


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


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return hmac.compare_digest(derived, expected)


class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: str
    terms_accepted: bool


class LoginRequest(BaseModel):
    email: str
    password: str


class WatchlistRequest(BaseModel):
    user_id: int
    symbol: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class ResendRequest(BaseModel):
    email: str


@router.post("/auth/signup")
def signup(req: SignupRequest):
    if not req.terms_accepted:
        raise HTTPException(status_code=400, detail="you must accept the Terms of Service and Privacy Policy")
    if not req.full_name.strip():
        raise HTTPException(status_code=400, detail="full name is required")
    if not req.phone.strip():
        raise HTTPException(status_code=400, detail="phone number is required")

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
                req.full_name.strip(),
                req.phone.strip(),
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
def verify_code(req: VerifyCodeRequest):
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, verified, verification_token FROM users WHERE email = ?", (req.email,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="no account for that email")
        if row["verified"]:
            return {"ok": True, "verified": True}
        if not row["verification_token"] or req.code.strip() != row["verification_token"]:
            raise HTTPException(status_code=400, detail="incorrect verification code")
        conn.execute("UPDATE users SET verified = 1, verification_token = NULL WHERE id = ?", (row["id"],))
    return {"ok": True, "verified": True}


@router.post("/auth/resend-code")
def resend_code(req: ResendRequest):
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
def login(req: LoginRequest):
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, is_admin, plan, verified, full_name, pending_plan "
            "FROM users WHERE email = ?",
            (req.email,),
        ).fetchone()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")
    if not row["verified"]:
        raise HTTPException(status_code=403, detail="email not verified")
    return {
        "id": row["id"],
        "email": row["email"],
        "is_admin": bool(row["is_admin"]),
        "plan": row["plan"],
        "full_name": row["full_name"],
        "pending_plan": row["pending_plan"],
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
