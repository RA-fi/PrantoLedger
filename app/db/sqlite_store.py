"""SQLite local store: audit log, decision cache, safety flags (PRD §11).

Pure stdlib sqlite3. Single-process so a single global lock is fine.
Best-effort logging — DB failures are swallowed so the HTTP response is
never blocked by the audit log.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


log = logging.getLogger("prantoledger.sqlite")

DB_PATH = os.getenv("AUDIT_DB_PATH", "./data/auditor.db")
_LOCK = threading.Lock()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL DEFAULT (datetime('now')),
    ticket_id       TEXT    NOT NULL,
    request_hash    TEXT    NOT NULL,
    verdict         TEXT    NOT NULL,
    case_type       TEXT    NOT NULL,
    severity        TEXT    NOT NULL,
    department      TEXT    NOT NULL,
    human_review    INTEGER NOT NULL,
    safety_flags    TEXT    NOT NULL DEFAULT '',
    latency_ms      INTEGER NOT NULL,
    used_llm        INTEGER NOT NULL DEFAULT 0,
    groq_attempts   INTEGER NOT NULL DEFAULT 0,
    groq_last_alias TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_audit_ticket ON audit_log(ticket_id);

CREATE TABLE IF NOT EXISTS decision_cache (
    request_hash    TEXT PRIMARY KEY,
    response_json   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS safety_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL DEFAULT (datetime('now')),
    ticket_id       TEXT NOT NULL,
    flag_kind       TEXT NOT NULL,
    snippet         TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Connection / init
# ---------------------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    # `isolation_level=None` puts us in autocommit mode — we issue explicit
    # BEGIN/COMMIT in the helpers below for safety.
    c = sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    """Create tables if missing. Idempotent. Best-effort chmod 600."""
    try:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    except OSError:
        pass
    try:
        with _LOCK, _connect() as c:
            c.executescript(SCHEMA_SQL)
        # Best-effort restrictive mode — harmless on Windows.
        try:
            os.chmod(DB_PATH, 0o600)
        except OSError:
            pass
    except Exception as e:  # pragma: no cover — only fires on weird FS
        log.warning("init_db failed: %s", e)


# ---------------------------------------------------------------------------
# Cache key + cache read/write
# ---------------------------------------------------------------------------


def cache_key(complaint: str, history: List[Dict[str, Any]]) -> str:
    """Stable hash of the canonicalised complaint + history."""
    canon = json.dumps(
        {"c": complaint, "h": history},
        sort_keys=True,
        default=str,
        ensure_ascii=False,
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def get_cached(key: str) -> Optional[Dict[str, Any]]:
    try:
        with _LOCK, _connect() as c:
            row = c.execute(
                "SELECT response_json FROM decision_cache WHERE request_hash=?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            return json.loads(row["response_json"])
    except Exception as e:
        log.warning("get_cached failed: %s", e)
        return None


def put_cached(key: str, response: Dict[str, Any]) -> None:
    try:
        with _LOCK, _connect() as c:
            c.execute(
                "INSERT OR REPLACE INTO decision_cache(request_hash, response_json) "
                "VALUES(?,?)",
                (key, json.dumps(response, ensure_ascii=False)),
            )
    except Exception as e:
        log.warning("put_cached failed: %s", e)


# ---------------------------------------------------------------------------
# Audit log + safety flags
# ---------------------------------------------------------------------------


def log_audit(row: Dict[str, Any]) -> None:
    """Insert one row per /analyze-ticket call. All fields optional except
    ticket_id / request_hash / verdict / case_type / severity / department /
    human_review / latency_ms."""
    try:
        with _LOCK, _connect() as c:
            c.execute(
                """
                INSERT INTO audit_log(
                    ticket_id, request_hash, verdict, case_type, severity,
                    department, human_review, safety_flags, latency_ms,
                    used_llm, groq_attempts, groq_last_alias
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["ticket_id"],
                    row["request_hash"],
                    row["verdict"],
                    row["case_type"],
                    row["severity"],
                    row["department"],
                    int(bool(row["human_review"])),
                    row.get("safety_flags", "") or "",
                    int(row["latency_ms"]),
                    int(bool(row.get("used_llm", False))),
                    int(row.get("groq_attempts", 0)),
                    row.get("groq_last_alias", "") or "",
                ),
            )
    except Exception as e:
        log.warning("log_audit failed: %s", e)


def flag_safety(ticket_id: str, kind: str, snippet: str) -> None:
    """Persist a 200-char safety snippet (PRD §11.3)."""
    try:
        with _LOCK, _connect() as c:
            c.execute(
                "INSERT INTO safety_flags(ticket_id, flag_kind, snippet) VALUES(?,?,?)",
                (ticket_id, kind, (snippet or "")[:200]),
            )
    except Exception as e:
        log.warning("flag_safety failed: %s", e)