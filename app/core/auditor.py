"""Deterministic rule-based auditor (PRD §7 — the 35-point core).

Pure stdlib, no I/O, no LLM. Returns an AuditResult describing what the
complaint *plus the supplied transaction history* actually shows. The
classifier downstream turns that into categorical decisions.

Critical invariant: this module NEVER raises. The orchestrator wraps every
call, but defensive coding keeps the auditor robust against weird inputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from .language import normalize_bangla_digits
from ..schemas import (
    AnalyzeTicketRequest,
    TransactionHistoryEntry,
)


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

# Tolerance for float-equality on BDT amounts (PRD §7.1 amount_matches).
AMOUNT_TOLERANCE = 0.01

# Two completed transfers within this window => duplicate_payment (PRD §7.1).
DUPLICATE_WINDOW_SECONDS = 60

# "wrong" / "ভুল" / common Banglish markers used to flag wrong-transfer intent.
WRONG_KEYWORDS = re.compile(
    r"\b(wrong|mistake|by mistake|wrong number|incorrect|"
    r"ভুল|ভুল নম্বর|ভুল নাম্বার|wrong person|wrong recipient)\b",
    re.IGNORECASE,
)

# "didn't get it" / "not received" markers — used as a *fallback* for ambiguity
# detection when there is no explicit "wrong" keyword but the customer is
# implying that money did not reach the intended recipient (SAMPLE-08).
NOT_RECEIVED_KEYWORDS = re.compile(
    r"\b(didn'?t (get|receive)|hasn'?t (got|received)|not (get|received)|"
    r"never (got|received)|"
    r"পায়নি|পাইনি|পাইছে না|আসেনি)\b",
    re.IGNORECASE,
)

# "refund" / "ফেরত" / "টাকা ফেরত" markers for refund_request path.
REFUND_KEYWORDS = re.compile(
    r"\b(refund|return (my|the) money|chargeback|"
    r"ফেরত|টাকা ফেরত|ফেরত দিন|ফেরত দিবেন)\b",
    re.IGNORECASE,
)

# "balance deducted" / "টাকা কেটে নিয়েছে" markers for status-conflict check.
DEDUCTED_KEYWORDS = re.compile(
    r"\b(balance (was )?deduct(ed|ion)?|money (was )?deducted|"
    r"amount (was )?deducted|deduct(ion)? from (my|the) (balance|account)|"
    r"টাকা কেটে নিয়েছে|ব্যালেন্স কমে গেছে|ব্যালেন্স কাটা)\b",
    re.IGNORECASE,
)

# Generic amount extractor: 5000 taka / ২,০০০ টাকা / Tk 500 / 500 BDT.
_AMOUNT_PATTERN = re.compile(
    r"(?P<amt>\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s*(?:taka|taka\b|tk|টাকা|bdt|BDT)",
    re.IGNORECASE,
)

# Fallback pattern: a bare number preceded by a money verb and followed by a
# transfer-like context. Used when the explicit currency suffix is missing in
# English complaints like "I sent 2000 to the wrong person".
_AMOUNT_FALLBACK = re.compile(
    r"\b(?:sent|paid|transferred|paid|lost|deposited|cash[ -]?in(?:ed)?|"
    r"recharged|top[ -]?up(?:ped)?|got|received|deduct(?:ed)?|charged)\b"
    r"\s+(?P<amt>\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)


def _parse_amount_from_complaint(complaint: str) -> Optional[float]:
    """Best-effort amount extraction. Returns the first numeric amount
    found near a currency suffix, or after a money verb (English), or None.
    Handles Bangla digits.
    """
    if not complaint:
        return None
    text = normalize_bangla_digits(complaint)
    m = _AMOUNT_PATTERN.search(text)
    if m is None:
        m = _AMOUNT_FALLBACK.search(text)
    if m is None:
        return None
    raw = m.group("amt").replace(",", "").replace(" ", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp, tolerating trailing Z."""
    if not ts:
        return None
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _sorted_by_time(history: List[TransactionHistoryEntry]) -> List[TransactionHistoryEntry]:
    """Return history sorted ascending by timestamp. Stable on parse errors."""
    parsed: List[Tuple[Optional[datetime], TransactionHistoryEntry]] = [
        (_parse_iso(t.timestamp), t) for t in history
    ]
    # None timestamps go last (treated as unknown).
    parsed.sort(key=lambda p: (p[0] is None, p[0] or datetime.min.replace(tzinfo=timezone.utc)))
    return [p[1] for p in parsed]


def _amount_matches(amount: Optional[float], history: List[TransactionHistoryEntry]) -> List[TransactionHistoryEntry]:
    """Filter history to entries whose amount is within AMOUNT_TOLERANCE."""
    if amount is None:
        return []
    return [tx for tx in history if abs(float(tx.amount) - amount) < AMOUNT_TOLERANCE]


# ---------------------------------------------------------------------------
# AuditResult — what the auditor decides (categorisation done downstream)
# ---------------------------------------------------------------------------

@dataclass
class AuditResult:
    """Structured findings of the rule engine. Pure data, no enums here."""

    # What the complaint said, normalised.
    complaint_amount: Optional[float] = None
    has_wrong_keyword: bool = False
    has_refund_keyword: bool = False
    has_deducted_keyword: bool = False
    has_not_received_keyword: bool = False

    # What the transaction history actually shows.
    history_empty: bool = False
    amount_matches: List[TransactionHistoryEntry] = field(default_factory=list)
    history_sorted: List[TransactionHistoryEntry] = field(default_factory=list)

    # Pre-classification flags derived from §7 decision tree.
    phishing: bool = False
    duplicate: Optional[TransactionHistoryEntry] = None       # the SECOND entry
    wrong_transfer_pattern: bool = False                     # established recipient
    ambiguous_match: bool = False                            # >=2 matches, diff counterparties
    status_conflict: Optional[TransactionHistoryEntry] = None  # failed + "deducted"
    pending_settlement: Optional[TransactionHistoryEntry] = None
    pending_cash_in: Optional[TransactionHistoryEntry] = None
    refund_match: Optional[TransactionHistoryEntry] = None
    single_wrong_transfer: Optional[TransactionHistoryEntry] = None

    # Diagnostics.
    reason_codes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_audit(req: AnalyzeTicketRequest, phishing_flag: bool = False) -> AuditResult:
    """Run the §7 decision tree against the request. Always returns an AuditResult."""
    result = AuditResult()
    complaint = req.complaint or ""

    result.phishing = phishing_flag
    result.history_empty = not req.transaction_history
    result.history_sorted = _sorted_by_time(req.transaction_history or [])

    result.complaint_amount = _parse_amount_from_complaint(complaint)
    result.has_wrong_keyword = bool(WRONG_KEYWORDS.search(complaint))
    result.has_refund_keyword = bool(REFUND_KEYWORDS.search(complaint))
    result.has_deducted_keyword = bool(DEDUCTED_KEYWORDS.search(complaint))
    result.has_not_received_keyword = bool(NOT_RECEIVED_KEYWORDS.search(complaint))

    if result.history_empty:
        if result.phishing:
            result.reason_codes.append("phishing_keywords_detected")
            result.reason_codes.append("empty_transaction_history")
        else:
            result.reason_codes.append("empty_transaction_history")
            result.reason_codes.append("vague_complaint")
        return result

    # Amount-matching step (used by most downstream checks).
    result.amount_matches = _amount_matches(result.complaint_amount, result.history_sorted)

    # ---- Duplicate-payment check (SAMPLE-10, two completed txs ≤ 60s) --------
    result.duplicate = _detect_duplicate(result.history_sorted)

    # ---- Wrong-transfer "established recipient" pattern (SAMPLE-02) ------------
    # The customer says "wrong transfer" but the same counterparty has been paid
    # multiple times before — that suggests an established recipient and the
    # claim is inconsistent with the transaction pattern.
    if result.has_wrong_keyword and result.amount_matches:
        cp = result.amount_matches[0].counterparty
        prior_completed = [
            tx for tx in result.history_sorted
            if tx.transaction_type.value == "transfer"
            and tx.status.value == "completed"
            and tx.counterparty == cp
            and tx.transaction_id != result.amount_matches[0].transaction_id
        ]
        if len(prior_completed) >= 2:
            result.wrong_transfer_pattern = True
            result.reason_codes.append("established_recipient_pattern")
            result.reason_codes.append("tx_match")

    # ---- Ambiguity check (SAMPLE-08) -------------------------------------------
    # Multiple matches across different counterparties => ambiguous. Either an
    # explicit "wrong" claim OR an implicit "didn't receive" claim is enough to
    # justify the disambiguation path.
    distinct_counterparties = {tx.counterparty for tx in result.amount_matches}
    if (
        len(result.amount_matches) >= 2
        and len(distinct_counterparties) >= 2
        and (result.has_wrong_keyword or result.has_not_received_keyword)
    ):
        result.ambiguous_match = True
        result.reason_codes.append("ambiguous_match")

    # ---- Status-conflict check (SAMPLE-03) -------------------------------------
    for tx in result.amount_matches:
        if tx.status.value == "failed" and result.has_deducted_keyword:
            result.status_conflict = tx
            result.reason_codes.append("status_contradicts_complaint")
            result.reason_codes.append("tx_match")
            break

    # ---- Pending settlement check (SAMPLE-09) ---------------------------------
    for tx in result.amount_matches:
        if tx.transaction_type.value == "settlement" and tx.status.value == "pending":
            result.pending_settlement = tx
            result.reason_codes.append("pending_settlement")
            result.reason_codes.append("tx_match")
            break

    # ---- Agent cash-in pending check (SAMPLE-07) ------------------------------
    for tx in result.amount_matches:
        if (
            tx.transaction_type.value == "cash_in"
            and tx.status.value == "pending"
            and tx.counterparty.upper().startswith("AGENT-")
        ):
            result.pending_cash_in = tx
            result.reason_codes.append("pending_cash_in")
            result.reason_codes.append("tx_match")
            break

    # ---- Refund-request check (SAMPLE-04) -------------------------------------
    if result.has_refund_keyword:
        for tx in result.amount_matches:
            if tx.transaction_type.value == "payment" and tx.status.value == "completed":
                result.refund_match = tx
                result.reason_codes.append("refund_request_match")
                break

    # ---- Single wrong-transfer check (SAMPLE-01) ------------------------------
    if (
        result.has_wrong_keyword
        and len(result.amount_matches) == 1
        and result.amount_matches[0].type.value == "transfer"
        and not result.ambiguous_match
        and not result.wrong_transfer_pattern
    ):
        result.single_wrong_transfer = result.amount_matches[0]
        result.reason_codes.append("tx_match")

    # Reason codes for duplicate (added last so they're easy to find).
    if result.duplicate is not None:
        result.reason_codes.append("duplicate_detected")
        result.reason_codes.append("tx_match")

    # Fallback reason code when nothing matched and the complaint was vague.
    if not result.reason_codes:
        if result.complaint_amount is None:
            result.reason_codes.append("vague_complaint")
        else:
            result.reason_codes.append("tx_match")

    return result


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_duplicate(history: List[TransactionHistoryEntry]) -> Optional[TransactionHistoryEntry]:
    """Return the SECOND of two same-type/same-counterparty completed entries
    whose timestamps are within DUPLICATE_WINDOW_SECONDS.
    """
    for i in range(len(history) - 1):
        a = history[i]
        b = history[i + 1]
        if (
            a.status.value == "completed"
            and b.status.value == "completed"
            and a.type == b.type
            and a.counterparty == b.counterparty
            and abs(a.amount - b.amount) < AMOUNT_TOLERANCE
        ):
            ta = _parse_iso(a.timestamp)
            tb = _parse_iso(b.timestamp)
            if ta is None or tb is None:
                continue
            if abs((tb - ta).total_seconds()) <= DUPLICATE_WINDOW_SECONDS:
                return b  # the SECOND entry is the suspected duplicate
    return None