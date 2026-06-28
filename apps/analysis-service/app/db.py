import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# DB location. Override with DB_PATH in production (e.g. on Railway set
# DB_PATH=/app/data/trade_insight.db and mount a volume at /app/data).
DB_PATH = Path(os.environ.get("DB_PATH") or (Path(__file__).resolve().parents[3] / "data" / "trade_insight.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    plan TEXT NOT NULL DEFAULT 'free',
    pending_plan TEXT,                  -- downgrade/cancel scheduled for period end
    plan_period_end TEXT,               -- when the current paid plan's period ends
    verified INTEGER NOT NULL DEFAULT 0,
    verification_token TEXT,
    api_key TEXT,
    full_name TEXT,
    phone TEXT,
    terms_accepted_at TEXT,
    monthly_uploads_used INTEGER NOT NULL DEFAULT 0,
    uploads_reset_at TEXT,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    lock_until TEXT,
    oauth_provider TEXT,                -- e.g. 'google' if created via OAuth (no password login)
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watchlist (
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    PRIMARY KEY (user_id, symbol),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL,
    PRIMARY KEY (symbol, interval, ts)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    direction TEXT NOT NULL,
    confluence_score INTEGER NOT NULL,
    reasoning_json TEXT NOT NULL,
    backtest_hit_rate REAL,
    timeframes_agreed TEXT,
    news_sentiment TEXT,
    interval TEXT,
    tier TEXT,
    entry REAL,
    stop_loss REAL,
    take_profit REAL,
    risk_reward REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-user config for the automated PAPER-trading bot (no real money/orders).
CREATE TABLE IF NOT EXISTS auto_trade_settings (
    user_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    max_open INTEGER NOT NULL DEFAULT 5,
    only_high_confidence INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Simulated positions opened automatically from signals. Purely hypothetical.
CREATE TABLE IF NOT EXISTS auto_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    signal_id INTEGER,
    symbol TEXT NOT NULL,
    interval TEXT,
    direction TEXT NOT NULL,
    entry REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',     -- open | closed
    outcome TEXT,                            -- win | loss | open
    exit_price REAL,
    pnl_pct REAL,
    venue TEXT NOT NULL DEFAULT 'simulated', -- simulated | demo | live-pending
    broker_ref TEXT,                         -- broker order id when executed on a demo account
    learned INTEGER NOT NULL DEFAULT 0,      -- 1 once its outcome fed the learning loop
    opened_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT
);

-- A user's connected brokerage. Demo accounts get authentic auto-execution;
-- live accounts are accepted only with an explicit risk waiver and NEVER get
-- autonomous real-money execution (orders require manual per-trade confirmation).
CREATE TABLE IF NOT EXISTS broker_connections (
    user_id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'simulated',  -- simulated | oanda
    mode TEXT NOT NULL DEFAULT 'demo',           -- demo | live
    account_id TEXT,
    token TEXT,
    risk_acknowledged INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Adaptive "learning": each strategy's measured win record drives the weight
-- it gets in the consensus. Updated from closed paper trades over time.
CREATE TABLE IF NOT EXISTS strategy_weights (
    name TEXT PRIMARY KEY,
    wins INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    weight REAL NOT NULL DEFAULT 1.0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Columns added over time — applied to existing DBs so a persisted volume
# (which keeps an older schema) gets upgraded safely on boot.
_MIGRATIONS = [
    ("users", "plan", "TEXT NOT NULL DEFAULT 'free'"),
    ("users", "verified", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "verification_token", "TEXT"),
    ("users", "api_key", "TEXT"),
    ("signals", "interval", "TEXT"),
    ("signals", "tier", "TEXT"),
    ("signals", "entry", "REAL"),
    ("signals", "stop_loss", "REAL"),
    ("signals", "take_profit", "REAL"),
    ("signals", "risk_reward", "REAL"),
    ("auto_trades", "venue", "TEXT NOT NULL DEFAULT 'simulated'"),
    ("auto_trades", "broker_ref", "TEXT"),
    ("auto_trades", "learned", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "pending_plan", "TEXT"),
    ("users", "plan_period_end", "TEXT"),
    ("users", "full_name", "TEXT"),
    ("users", "phone", "TEXT"),
    ("users", "terms_accepted_at", "TEXT"),
    ("users", "monthly_uploads_used", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "uploads_reset_at", "TEXT"),
    ("users", "failed_login_attempts", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "lock_until", "TEXT"),
    ("users", "oauth_provider", "TEXT"),
]


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # idempotent column migrations for pre-existing databases
        for table, column, decl in _MIGRATIONS:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            except sqlite3.OperationalError:
                pass  # column already exists


@contextmanager
def db_session():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
