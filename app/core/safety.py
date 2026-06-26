"""Three-layer safety: pre-LLM injection filter, phishing scanner, post-LLM
sanitizer (PRD §9).

All regexes are intentionally narrow so they trigger on obvious attack
shapes only — over-matching risks false positives on legitimate
"refund please" wording and false negatives on novel rephrasings.
"""

from __future__ import annotations

import re
from typing import Tuple

# ---------------------------------------------------------------------------
# 9.1 Prompt-injection filter
# ---------------------------------------------------------------------------

INJECTION_PATTERNS = re.compile(
    r"(ignore|override|bypass|forget)\s+(previous|system|all|my)\s+"
    r"(instructions|rules|prompts|parameters)"
    r"|you are now\b|new role\b|do not follow\b"
    r"|confirm a refund\b|state that a refund has been credited\b"
    r"|reveal (your|the) (system|prompt|instructions)\b"
    r"|disregard (your|the) (rules|policy|policies)\b",
    re.IGNORECASE,
)


def is_injection(text: str) -> bool:
    """True if `text` contains a clear prompt-injection attempt."""
    if not text:
        return False
    return bool(INJECTION_PATTERNS.search(text))


# ---------------------------------------------------------------------------
# 9.2 Phishing keyword scanner (English + Bangla)
# ---------------------------------------------------------------------------

PHISHING_PATTERNS = re.compile(
    r"\b(otp|pin|password|cvv|one[- ]time password|"
    r"send (me )?(your|the) (otp|pin))"
    r"|কেউ (ফোন|মেসেজ) করে (পিন|ওটিপি|পাসওয়ার্ড) চাচ্ছে"
    r"|আমার (একাউন্ট|হিসাব) (ব্লক|বন্ধ) হয়ে যাবে"
    r"|share (your|the) (otp|pin|password)"
    r"|asking for (my|our) (otp|pin|password)\b",
    re.IGNORECASE,
)


def is_phishing(text: str) -> bool:
    """True if `text` reports a credential-request or social-engineering event."""
    if not text:
        return False
    return bool(PHISHING_PATTERNS.search(text))


# ---------------------------------------------------------------------------
# 9.3 Post-LLM compliance sanitizer
# ---------------------------------------------------------------------------

PIN_OTP_REQUEST = re.compile(
    r"\b(send|share|tell|give|provide|type|enter)\b"
    r".{0,30}\b(pin|otp|one[- ]time password|password|cvv|card number|পিন|ওটিপি)\b",
    re.IGNORECASE,
)

REFUND_PROMISE = re.compile(
    r"\b(we (will|have|are going to) (refund|reverse|credit|return))"
    r"|\b(refunded successfully|refunded your|credited your account|"
    r"reverse your payment|টাকা ফেরত দেওয়া হয়েছে|টাকা ফেরত দিচ্ছি)\b",
    re.IGNORECASE,
)

UNOFFICIAL_CHANNEL = re.compile(
    r"\b(whatsapp|telegram|t\.me|fb\.com|tinyurl|bit\.ly|"
    r"call me at \+?9|contact me on|message me on)\b",
    re.IGNORECASE,
)

# Generic safe reply used whenever sanitizer fires on a PIN/OTP request.
SAFE_REPLY_FALLBACK = (
    "We have received your request. For your security, please do not share your "
    "PIN or OTP with anyone. Our support team will review the case and contact "
    "you through official support channels."
)


def sanitize(reply: str, action: str) -> Tuple[str, str]:
    """Return (reply, action) with any forbidden language stripped to safe
    equivalents. Each rule is independent: violations stack, never crash.
    """
    safe_reply = reply
    safe_action = action

    if PIN_OTP_REQUEST.search(safe_reply) or PIN_OTP_REQUEST.search(safe_action):
        safe_reply = SAFE_REPLY_FALLBACK

    if REFUND_PROMISE.search(safe_reply) or REFUND_PROMISE.search(safe_action):
        safe_reply = (
            "We have logged your dispute. Any eligible amount will be returned "
            "through official channels after verification. Please do not share "
            "your PIN or OTP with anyone."
        )
        safe_action = (
            "Verify ledger state and initiate the standard refund dispute "
            "workflow through official channels."
        )

    if UNOFFICIAL_CHANNEL.search(safe_reply):
        safe_reply = (
            "We have received your request. Please contact us only through our "
            "official support hotline or the in-app help desk."
        )

    return safe_reply, safe_action


# ---------------------------------------------------------------------------
# Fallback payloads (PRD §9.1)
# ---------------------------------------------------------------------------

def injection_fallback_payload(ticket_id: str) -> dict:
    """Safe payload returned when prompt-injection is detected."""
    return {
        "ticket_id": ticket_id,
        "relevant_transaction_id": None,
        "evidence_verdict": "insufficient_data",
        "case_type": "phishing_or_social_engineering",
        "severity": "critical",
        "department": "fraud_risk",
        "agent_summary": (
            "Pre-LLM system audit flagged potential prompt injection or "
            "unauthorized system override command."
        ),
        "recommended_next_action": (
            "Bypass LLM, route ticket to security team, and log sender's "
            "metadata for fraud review."
        ),
        "customer_reply": (
            "We have detected unusual activity. Your request has been sent to "
            "our security team. Please do not share your account credentials "
            "with anyone."
        ),
        "human_review_required": True,
        "confidence": 1.0,
        "reason_codes": ["prompt_injection_blocked", "security_bypass"],
    }