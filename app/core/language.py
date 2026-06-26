"""Language detection and Bangla digit normalisation (PRD §8.1, §8.2).

Pure stdlib, no external API. Used by the orchestrator to pick a template
language and to normalise amounts before amount extraction.
"""

from __future__ import annotations

import re
from typing import Optional

# Bangla Unicode block (U+0980..U+09FF).
BANGLA_UNICODE = re.compile(r"[\u0980-\u09FF]")

# Banglish romanisation markers we treat as "mixed". This is intentionally
# conservative so a pure-English complaint does not get misclassified.
_BANGLISH_TOKENS = re.compile(
    r"\b(ami|amar|taka|tk|din|kal|aj|wrong number|"
    r"bhai|apni|keno|keno|tui|tui|lagbe|chai|"
    r"taka pathacchi|taka pathiyechen|keteche|"
    r"porer|ekhon|ekhon)\b",
    re.IGNORECASE,
)

_BN_TO_ASCII = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def detect_language(text: str, hint: Optional[str]) -> str:
    """Return 'en' | 'bn' | 'mixed' for the given complaint text.

    The harness-supplied `language` hint, when present and one of the allowed
    enums, is trusted. Otherwise we fall back to a deterministic text scan.
    """
    if hint in ("en", "bn", "mixed"):
        return hint
    if not text:
        return "en"
    if BANGLA_UNICODE.search(text):
        return "bn"
    if _BANGLISH_TOKENS.search(text):
        return "mixed"
    return "en"


def normalize_bangla_digits(text: str) -> str:
    """Translate Bangla digits (০-৯) to ASCII so downstream regex works."""
    return text.translate(_BN_TO_ASCII)