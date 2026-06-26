"""Pytest suite for PrantoLedger.

Strategy (PRD §16):
- Each of the 10 public samples from docs/SUST_Preli_Sample_Cases.json is POSTed
  through the full /analyze-ticket pipeline.
- We compare against expected_output on the *semantic* fields:
    * relevant_transaction_id (exact)
    * evidence_verdict (exact)
    * case_type (exact)
    * department (exact)
    * severity (one-of {expected, expected+/-1 step on the low→critical scale})
    * human_review_required (bool)
    * customer_reply (must be safe — no PIN/OTP requests, no refund promises)
- Safety tests in test_safety.py cover the pre-LLM injection short-circuit and
  the phishing keyword scanner.

We use TestClient from FastAPI (synchronous) so the whole test file runs in one
thread and we never hit the real network (no Groq keys are loaded).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test fixtures — isolate SQLite to a tmp file
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    tmp_dir = tempfile.mkdtemp(prefix="prantoledger-test-")
    os.environ["AUDIT_DB_PATH"] = os.path.join(tmp_dir, "auditor.db")
    # Ensure no Groq key is loaded — the test must not call the network.
    os.environ.pop("GROQ_API_KEY", None)
    os.environ.pop("GROQ_API_KEYS", None)

    # Re-import the app lazily so the new env takes effect.
    from app.main import app  # noqa: WPS433 — intentional test-local import

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Load the 10 sample cases
# ---------------------------------------------------------------------------


SAMPLES_PATH = Path(__file__).resolve().parent.parent / "docs" / "SUST_Preli_Sample_Cases.json"


@pytest.fixture(scope="module")
def samples():
    with SAMPLES_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


# Severity ordering for "comparable" tolerance in sample validation.
SEVERITY_ORDER = ["low", "medium", "high", "critical"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_safe_reply(text: str) -> None:
    """`customer_reply` must never request credentials or promise a refund.

    Two-pass check:
      1) find any imperative credential request in the text;
      2) reject it only if the match is NOT preceded (within a small window)
         by a defensive phrase like "do not", "never", "don't".
    Defensive wording like "please do not share your PIN" is exactly what we
    want and must not trip the check.
    """
    import re as _re

    lower = text.lower()

    imperative_patterns = [
        r"\bsend (?:me )?(?:your|the) (?:pin|otp|one[- ]time password|password|cvv)\b",
        r"\bshare (?:your|the) (?:pin|otp|one[- ]time password|password|cvv)\b",
        r"\b(?:tell|give|provide|type|enter) (?:me )?(?:your|the) (?:pin|otp|one[- ]time password|password|cvv)\b",
    ]
    defensive_prefixes = [
        r"do not",
        r"don'?t",
        r"never",
        r"please do not",
    ]

    for pat in imperative_patterns:
        for m in _re.finditer(pat, lower):
            # Look at the 20 characters immediately before the match.
            start = max(0, m.start() - 20)
            window = lower[start:m.start()]
            if any(_re.search(p, window) for p in defensive_prefixes):
                continue  # defensive phrasing — this is good
            raise AssertionError(
                f"unsafe imperative credential request in reply: "
                f"{lower[m.start():m.end()]!r} in {text!r}"
            )

    # Refund-promise check: a *commitment* is forbidden.
    forbidden_commitments = [
        r"\bwe'?ll refund\b",
        r"\brefunded (?:your|the)\b",
        r"\bcredited your account\b",
    ]
    for pat in forbidden_commitments:
        assert not _re.search(pat, lower), (
            f"unauthorised refund commitment /{pat}/ in {text!r}"
        )


def _severity_compatible(actual: str, expected: str) -> bool:
    """Allow exact match or a one-step drift either way."""
    if actual == expected:
        return True
    try:
        ai = SEVERITY_ORDER.index(actual)
        ei = SEVERITY_ORDER.index(expected)
    except ValueError:
        return False
    return abs(ai - ei) <= 1


# ---------------------------------------------------------------------------
# Sample tests — one per case in the public pack
# ---------------------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["llm_pool"]["size"] == 0  # no GROQ_API_KEYS in test env


@pytest.mark.parametrize("case_index", list(range(10)))
def test_sample_case(client, samples, case_index):
    case = samples[case_index]
    assert "input" in case and "expected_output" in case, f"case {case_index} malformed"
    inp = case["input"]
    exp = case["expected_output"]

    # Cache from earlier cases in the same test module must not poison results:
    # each sample uses unique amounts/timestamps so this is a non-issue, but we
    # also flush via unique ticket_ids which the API already echoes back.
    r = client.post("/analyze-ticket", json=inp)
    assert r.status_code == 200, f"case {case_index} HTTP {r.status}: {r.text}"

    got = r.json()
    assert got["ticket_id"] == inp["ticket_id"]

    # --- Exact fields per PRD §16 -------------------------------------------
    assert got["relevant_transaction_id"] == exp["relevant_transaction_id"], (
        f"case {case_index} ({case.get('id')}): "
        f"relevant_transaction_id {got['relevant_transaction_id']!r} != {exp['relevant_transaction_id']!r}"
    )
    assert got["evidence_verdict"] == exp["evidence_verdict"], (
        f"case {case_index} ({case.get('id')}): evidence_verdict mismatch"
    )
    assert got["case_type"] == exp["case_type"], (
        f"case {case_index} ({case.get('id')}): case_type {got['case_type']!r} != {exp['case_type']!r}"
    )
    assert got["department"] == exp["department"], (
        f"case {case_index} ({case.get('id')}): department {got['department']!r} != {exp['department']!r}"
    )
    assert got["human_review_required"] == exp["human_review_required"], (
        f"case {case_index} ({case.get('id')}): human_review_required mismatch"
    )

    # --- Comparable severity (±1 step) --------------------------------------
    assert _severity_compatible(got["severity"], exp["severity"]), (
        f"case {case_index} ({case.get('id')}): severity {got['severity']!r} vs expected {exp['severity']!r}"
    )

    # --- Mandatory non-empty text fields -----------------------------------
    assert len(got["agent_summary"]) >= 10
    assert len(got["recommended_next_action"]) >= 10
    assert len(got["customer_reply"]) >= 10

    # --- customer_reply safety invariant -----------------------------------
    _assert_safe_reply(got["customer_reply"])