"""Generic outbound email — shared by auth (verification codes) and mt5_bridge
(live-trade confirmation links). Reads the same SMTP/Resend env vars."""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText

import httpx


def _clean_env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name, default)
    if v is None:
        return None
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    return v


WEB_BASE_URL = _clean_env("WEB_BASE_URL", "http://localhost:3000")
RESEND_API_KEY = _clean_env("RESEND_API_KEY")
RESEND_FROM = _clean_env("RESEND_FROM", "PIP HIVE <onboarding@resend.dev>")
SMTP_USER = _clean_env("SMTP_USER")
# Gmail App Passwords are displayed with spaces (xxxx xxxx xxxx xxxx) but must
# be sent without them — strip all internal whitespace so copy-paste works.
_raw_pass = _clean_env("SMTP_PASS")
SMTP_PASS = _raw_pass.replace(" ", "") if _raw_pass else None
SMTP_HOST = _clean_env("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_clean_env("SMTP_PORT", "587"))
SMTP_FROM = _clean_env("SMTP_FROM") or SMTP_USER
EMAIL_CONFIGURED = bool(RESEND_API_KEY or (SMTP_USER and SMTP_PASS))


def send_email(to: str, subject: str, body: str) -> bool:
    """Send via Gmail/SMTP first, falling back to Resend. Returns True only if
    an email was actually sent."""
    if SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM or SMTP_USER
            msg["To"] = to
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
            return True
        except Exception as e:  # noqa: BLE001 — fall through to Resend
            print(f"[notify] SMTP send failed: {type(e).__name__}: {e}", flush=True)

    if RESEND_API_KEY:
        try:
            r = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={"from": RESEND_FROM, "to": [to], "subject": subject, "text": body},
                timeout=15,
            )
            return r.status_code < 300
        except Exception as e:  # noqa: BLE001
            print(f"[notify] Resend send failed: {type(e).__name__}: {e}", flush=True)

    return False
