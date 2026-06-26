"""Optional Groq wrapper with rotating key pool (PRD §10.5).

Key design rules:
- NEVER fatal: any failure (timeout, 4xx/5xx, JSON parse, network) falls
  back to the original template reply.
- NEVER logs or returns key values — only stable aliases (`key#1`, ...).
- Pool is opportunistic (skip cooling keys, fall through to next ready one).
- Hard cap: pool size capped at 8 to keep `8 × 3.5s = 28s < 30s` harness budget.
- Synchronous wrapper exposed via `maybe_polish` — FastAPI threadpool runs it
  so the event loop isn't blocked.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx


log = logging.getLogger("prantoledger.llm")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Per-key state machine.
STATE_READY = "ready"
STATE_COOLING = "cooling"

# Cooldowns (seconds) per failure class — PRD §10.5.4.
COOLDOWN_429 = 30
COOLDOWN_401 = 60
COOLDOWN_5XX = 15
COOLDOWN_TIMEOUT = 15
COOLDOWN_NETWORK = 15
COOLDOWN_MALFORMED = 15

# Pool cap: keep worst-case latency under 30s (PRD §10.5.5).
POOL_CAP = 8
# Per-attempt timeout — calibrated for the 70B model on free tier.
DEFAULT_TIMEOUT_S = 3.5


# ---------------------------------------------------------------------------
# Pool state
# ---------------------------------------------------------------------------


@dataclass
class _KeyState:
    alias: str
    value: str
    state: str = STATE_READY
    cooldown_until: float = 0.0  # epoch seconds
    used_in_window: int = 0


class _Pool:
    """Process-wide key pool. Thread-safe via a single lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: List[_KeyState] = []
        self._window_start = time.monotonic()
        self._window_used = 0

    # ----- setup -----------------------------------------------------------
    def load(self) -> None:
        """Read env once at startup. Idempotent."""
        with self._lock:
            if self._keys:
                return  # already loaded

            multi = os.getenv("GROQ_API_KEYS", "").strip()
            single = os.getenv("GROQ_API_KEY", "").strip()
            raw: List[str] = []

            if multi:
                # Allow comma-separated list, with optional "p1=...value" aliases.
                for piece in multi.split(","):
                    piece = piece.strip()
                    if not piece:
                        continue
                    if "=" in piece:
                        piece = piece.split("=", 1)[1].strip()
                    if piece:
                        raw.append(piece)
            elif single:
                raw.append(single)

            # Truncate to POOL_CAP (PRD §10.5.5).
            raw = raw[:POOL_CAP]

            self._keys = [
                _KeyState(alias=f"key#{i+1}", value=v) for i, v in enumerate(raw)
            ]

    # ----- accessors used by /health --------------------------------------
    def size(self) -> int:
        with self._lock:
            return len(self._keys)

    def ready_count(self) -> int:
        with self._lock:
            now = time.monotonic()
            return sum(
                1 for k in self._keys
                if k.state == STATE_READY or k.cooldown_until <= now
            )

    def used_in_window(self) -> int:
        """Reset the window every hour to keep the counter meaningful."""
        with self._lock:
            if time.monotonic() - self._window_start > 3600:
                self._window_start = time.monotonic()
                self._window_used = 0
            return self._window_used

    # ----- rotation --------------------------------------------------------
    def _bump_used(self) -> None:
        with self._lock:
            self._window_used += 1

    def _mark(self, alias: str, cooldown_s: int) -> None:
        with self._lock:
            for k in self._keys:
                if k.alias == alias:
                    k.state = STATE_COOLING
                    k.cooldown_until = time.monotonic() + cooldown_s
                    return

    def _is_ready(self, k: _KeyState) -> bool:
        if k.state == STATE_READY:
            return True
        # Opportunistic recovery — flip back to ready once cooldown elapsed.
        if time.monotonic() >= k.cooldown_until:
            k.state = STATE_READY
            return True
        return False

    def snapshot(self) -> List[_KeyState]:
        with self._lock:
            return list(self._keys)


# Module-level singleton. `load()` is called from app lifespan.
_POOL = _Pool()


def init_pool() -> None:
    """Initialise the key pool from environment. Safe to call repeatedly."""
    _POOL.load()


def pool_size() -> int:
    return _POOL.size()


def pool_ready() -> int:
    return _POOL.ready_count()


def pool_used() -> int:
    return _POOL.used_in_window()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@dataclass
class PolishResult:
    """Outcome of one LLM attempt — what the audit log needs."""

    text: str           # final reply (template if LLM skipped/failed)
    used_llm: bool
    groq_attempts: int
    groq_last_alias: str  # e.g. 'key#3' or '' if LLM skipped


def maybe_polish(template_reply: str, language: str) -> PolishResult:
    """Try to lightly paraphrase `template_reply` via Groq.

    Falls back to `template_reply` unchanged on any error. Synchronous so
    FastAPI's threadpool can run it.
    """
    _POOL.load()
    keys = [k for k in _POOL.snapshot() if _POOL._is_ready(k)]
    if not keys:
        return PolishResult(
            text=template_reply,
            used_llm=False,
            groq_attempts=0,
            groq_last_alias="",
        )

    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL)
    try:
        timeout_s = float(os.getenv("GROQ_TIMEOUT_S", str(DEFAULT_TIMEOUT_S)))
    except ValueError:
        timeout_s = DEFAULT_TIMEOUT_S

    last_alias = ""
    last_err = ""
    attempts = 0

    for k in keys:
        attempts += 1
        last_alias = k.alias
        _POOL._bump_used()

        try:
            with httpx.Client(timeout=timeout_s) as client:
                r = client.post(
                    GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {k.value}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "temperature": 0.0,
                        "max_tokens": 512,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Rewrite the following customer support reply "
                                    "in the same language, keep all safety constraints "
                                    "(no PIN/OTP request, no refund promise), keep it "
                                    "short, and never invent new financial commitments. "
                                    "Return only the rewritten text."
                                ),
                            },
                            {"role": "user", "content": template_reply},
                        ],
                    },
                )

            if r.status_code == 429:
                _POOL._mark(k.alias, COOLDOWN_429)
                last_err = f"{k.alias} -> HTTP 429"
                continue
            if r.status_code in (401, 403):
                _POOL._mark(k.alias, COOLDOWN_401)
                last_err = f"{k.alias} -> HTTP {r.status_code}"
                continue
            if 500 <= r.status_code < 600:
                _POOL._mark(k.alias, COOLDOWN_5XX)
                last_err = f"{k.alias} -> HTTP {r.status_code}"
                continue
            if r.status_code == 400:
                # Malformed payload — our bug, no point rotating.
                log.warning("groq 400 (malformed): alias=%s", k.alias)
                return PolishResult(
                    text=template_reply,
                    used_llm=False,
                    groq_attempts=attempts,
                    groq_last_alias=k.alias,
                )
            r.raise_for_status()
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            content = (content or "").strip()
            if not content:
                _POOL._mark(k.alias, COOLDOWN_MALFORMED)
                last_err = f"{k.alias} -> empty body"
                continue
            return PolishResult(
                text=content,
                used_llm=True,
                groq_attempts=attempts,
                groq_last_alias=k.alias,
            )

        except httpx.TimeoutException:
            _POOL._mark(k.alias, COOLDOWN_TIMEOUT)
            last_err = f"{k.alias} -> Timeout"
            continue
        except httpx.NetworkError:
            _POOL._mark(k.alias, COOLDOWN_NETWORK)
            last_err = f"{k.alias} -> NetworkError"
            continue
        except json.JSONDecodeError:
            _POOL._mark(k.alias, COOLDOWN_MALFORMED)
            last_err = f"{k.alias} -> JSONDecodeError"
            continue
        except Exception as e:  # last-resort guard — never fatal
            _POOL._mark(k.alias, COOLDOWN_NETWORK)
            last_err = f"{k.alias} -> {type(e).__name__}"
            continue

    # Pool exhausted or every key errored — return the safe template reply.
    if last_err:
        log.info("groq pool exhausted: %s", last_err)
    return PolishResult(
        text=template_reply,
        used_llm=False,
        groq_attempts=attempts,
        groq_last_alias=last_alias,
    )